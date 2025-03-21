import asyncio
import hashlib
import json
import os
from abc import ABC, abstractmethod
from datetime import datetime, timedelta, timezone
from typing import Dict, Any, Optional, Union, Tuple, List

import google.generativeai as genai
from google.api_core.exceptions import ResourceExhausted as GoogleAPIResourceExhausted
from google.cloud import bigquery
from openai import AsyncOpenAI

from utils.async_utils import to_thread, to_cpu_thread, run_in_thread
from utils.retry_utils import RetryableError, RetryConfig, with_retry
from utils.token_usage import TokenUsage
from utils.loguru_setup import logger


# Retry configurations
GEMINI_RETRY_CONFIG = RetryConfig(
    max_attempts=3,
    base_delay=2.0,
    max_delay=60.0,
    retryable_exceptions=[
        RetryableError,
        GoogleAPIResourceExhausted,
        ValueError,
        RuntimeError,
        TimeoutError,
        ConnectionError
    ]
)

OPENAI_RETRY_CONFIG = RetryConfig(
    max_attempts=3,
    base_delay=2.0,
    max_delay=30.0,
    retryable_exceptions=[
        RetryableError,
        ValueError,
        RuntimeError,
        TimeoutError,
        ConnectionError
    ]
)

class AICacheService:
    """Service for caching AI prompts and responses."""

    def __init__(self, client: bigquery.Client, project_id: str, dataset: str):
        """Initialize the AI cache service."""
        self.client = client
        self.project_id = project_id
        self.dataset = dataset
        self.table_name = "ai_prompt_cache"

    # This will be called when a task is created to ensure that the cache table always exists
    @to_thread
    def ensure_cache_table(self) -> None:
        """Create the cache table if it doesn't exist."""
        schema = [
            bigquery.SchemaField("cache_key", "STRING", mode="REQUIRED"),
            bigquery.SchemaField("provider", "STRING", mode="REQUIRED"),
            bigquery.SchemaField("model", "STRING", mode="REQUIRED"),
            bigquery.SchemaField("prompt", "STRING", mode="REQUIRED"),
            bigquery.SchemaField("is_json_response", "BOOLEAN", mode="REQUIRED"),
            bigquery.SchemaField("operation_tag", "STRING"),
            bigquery.SchemaField("temperature", "FLOAT"),  # Add temperature to schema
            bigquery.SchemaField("response_data", "JSON"),
            bigquery.SchemaField("response_text", "STRING"),
            bigquery.SchemaField("prompt_tokens", "INTEGER"),
            bigquery.SchemaField("completion_tokens", "INTEGER"),
            bigquery.SchemaField("total_tokens", "INTEGER"),
            bigquery.SchemaField("total_cost_in_usd", "FLOAT64"),
            bigquery.SchemaField("created_at", "TIMESTAMP", mode="REQUIRED"),
            bigquery.SchemaField("expires_at", "TIMESTAMP"),
            bigquery.SchemaField("tenant_id", "STRING"),
        ]

        table_id = f"{self.project_id}.{self.dataset}.{self.table_name}"
        try:
            self.client.get_table(table_id)
        except Exception:
            table = bigquery.Table(table_id, schema=schema)
            table = self.client.create_table(table)
            logger.info(f"Created table {table_id}")

    def _generate_cache_key(
            self,
            prompt: str,
            provider: str,
            model: str,
            is_json: bool,
            operation_tag: str,
            temperature: Optional[float] = None
    ) -> str:
        """Generate a unique cache key for the AI request including temperature."""
        cache_data = {
            'prompt': prompt,
            'provider': provider,
            'model': model,
            'is_json': is_json,
            'operation_tag': operation_tag,
            'temperature': temperature  # Include temperature in cache key
        }
        cache_str = json.dumps(cache_data, sort_keys=True)
        return hashlib.sha256(cache_str.encode()).hexdigest()

    async def get_cached_response(
            self,
            prompt: str,
            provider: str,
            model: str,
            is_json: bool = True,
            operation_tag: str = "default",
            tenant_id: Optional[str] = None,
            temperature: Optional[float] = None
    ) -> Optional[Dict[str, Any]]:
        """Get cached response for the given AI prompt."""
        cache_key = self._generate_cache_key(prompt, provider, model, is_json, operation_tag, temperature)

        query = f"""
        SELECT 
            response_data,
            response_text,
            prompt_tokens,
            completion_tokens,
            total_tokens,
            total_cost_in_usd
        FROM `{self.project_id}.{self.dataset}.{self.table_name}`
        WHERE cache_key = @cache_key
        AND provider = @provider
        AND model = @model
        AND is_json_response = @is_json
        AND (temperature IS NULL OR temperature = @temperature)
        AND (expires_at IS NULL OR expires_at > CURRENT_TIMESTAMP())
        AND (tenant_id IS NULL OR tenant_id = @tenant_id)
        ORDER BY created_at DESC
        LIMIT 1
        """

        job_config = bigquery.QueryJobConfig(
            query_parameters=[
                bigquery.ScalarQueryParameter("cache_key", "STRING", cache_key),
                bigquery.ScalarQueryParameter("provider", "STRING", provider),
                bigquery.ScalarQueryParameter("model", "STRING", model),
                bigquery.ScalarQueryParameter("is_json", "BOOL", is_json),
                bigquery.ScalarQueryParameter("tenant_id", "STRING", tenant_id),
                bigquery.ScalarQueryParameter("temperature", "FLOAT", temperature)
            ]
        )

        # Execute query in a separate thread
        results = await self._execute_query(query, job_config)
        if results:
            row = results[0]

            # Create token usage object
            token_usage = TokenUsage(
                operation_tag=operation_tag,
                prompt_tokens=row.prompt_tokens,
                completion_tokens=row.completion_tokens,
                total_tokens=row.total_tokens,
                total_cost_in_usd=row.total_cost_in_usd,
                provider=provider
            )

            # Parse the response based on type
            content = None
            if is_json:
                # BigQuery client already deserializes JSON fields
                content = row.response_data
            else:
                content = row.response_text

            return {
                "content": content,
                "token_usage": token_usage
            }

        return None

    @to_thread
    def _execute_query(self, query: str, job_config: bigquery.QueryJobConfig) -> List[Any]:
        """Execute a BigQuery query in a separate thread and return results"""
        return list(self.client.query(query, job_config=job_config).result())

    def _log_response_structure(self, response_data: Any) -> None:
        """Log detailed structure of response data including types of all values."""
        if not isinstance(response_data, dict):
            logger.debug(f"Response data is not a dict, type: {type(response_data)}")
            return

        # Log first-level keys and their value types
        type_info = {
            key: f"{type(value).__name__} ({len(value) if isinstance(value, (list, dict, str)) else 'N/A'})"
            for key, value in response_data.items()
        }
        logger.debug(f"Response data structure: {type_info}")

        # For nested structures, log more details
        for key, value in response_data.items():
            if isinstance(value, list) and value:
                # Log type of first item in list
                first_item = value[0]
                if isinstance(first_item, dict):
                    nested_types = {
                        nested_key: type(nested_value).__name__
                        for nested_key, nested_value in first_item.items()
                    }
                    logger.debug(f"First item in '{key}' list has structure: {nested_types}")
                else:
                    logger.debug(f"Items in '{key}' list are of type: {type(first_item).__name__}")
            elif isinstance(value, dict):
                nested_types = {
                    nested_key: type(nested_value).__name__
                    for nested_key, nested_value in value.items()
                }
                logger.debug(f"Nested structure for '{key}': {nested_types}")

    async def cache_response(
            self,
            prompt: str,
            response: Union[Dict[str, Any], str],
            token_usage: TokenUsage,
            provider: str,
            model: str,
            is_json: bool = True,
            operation_tag: str = "default",
            tenant_id: Optional[str] = None,
            ttl_hours: Optional[int] = None,
            temperature: Optional[float] = None
    ) -> None:
        """Cache an AI response."""
        cache_key = self._generate_cache_key(prompt, provider, model, is_json, operation_tag, temperature)
        expires_at = None

        if ttl_hours is not None:
            expires_at = datetime.now(timezone.utc) + timedelta(hours=ttl_hours)

        response_data = None
        response_text = None

        if is_json:
            # Handle JSON responses - explicitly serialize to JSON string
            if isinstance(response, dict):
                response_data = json.dumps(response)
            else:
                # For non-dict responses, wrap in a dict and serialize
                response_data = json.dumps({"data": str(response)})
        else:
            response_text = str(response)

        row = {
            "cache_key": cache_key,
            "provider": provider,
            "model": model,
            "prompt": prompt,
            "is_json_response": is_json,
            "operation_tag": operation_tag,
            "temperature": temperature,  # Store temperature value
            "response_data": response_data,  # Already JSON string
            "response_text": response_text,
            "prompt_tokens": token_usage.prompt_tokens,
            "completion_tokens": token_usage.completion_tokens,
            "total_tokens": token_usage.total_tokens,
            "total_cost_in_usd": token_usage.total_cost_in_usd,
            "created_at": datetime.now(timezone.utc).isoformat(),
            "expires_at": expires_at.isoformat() if expires_at else None,
            "tenant_id": tenant_id
        }

        # For debugging
        logger.debug(f"Inserting row with response_data type: {type(row['response_data'])}")

        # Insert row in a separate thread
        errors = await self._insert_row(row)

        if errors:
            logger.error(f"Error caching AI response: {errors}")
            logger.error(f"Failed row data: {json.dumps(row, default=str)}")
            raise Exception(f"Failed to cache AI response: {errors}")

    @to_thread
    def _insert_row(self, row: Dict[str, Any]) -> List[Any]:
        """Insert a row into the cache table in a separate thread"""
        table = self.client.get_table(f"{self.project_id}.{self.dataset}.{self.table_name}")
        return self.client.insert_rows_json(table, [row])

    async def clear_expired_cache(self, days: int = 30) -> int:
        """Clear expired cache entries and entries older than specified days."""
        query = f"""
        DELETE FROM `{self.project_id}.{self.dataset}.{self.table_name}`
        WHERE expires_at < CURRENT_TIMESTAMP()
        OR created_at < TIMESTAMP_SUB(CURRENT_TIMESTAMP(), INTERVAL @days DAY)
        """

        job_config = bigquery.QueryJobConfig(
            query_parameters=[
                bigquery.ScalarQueryParameter("days", "INTEGER", days)
            ]
        )

        # Execute delete query in a separate thread
        return await self._execute_delete_query(query, job_config)

    @to_thread
    def _execute_delete_query(self, query: str, job_config: bigquery.QueryJobConfig) -> int:
        """Execute a delete query in a separate thread and return affected rows"""
        query_job = self.client.query(query, job_config=job_config)
        query_job.result()
        return query_job.num_dml_affected_rows


class AIService(ABC):
    """Abstract base class for AI service providers."""

    def __init__(
            self,
            model_name: Optional[str] = None,
            cache_service: Optional[AICacheService] = None,
            tenant_id: Optional[str] = None,
            default_temperature: Optional[float] = None
    ):
        """Initialize service with token tracking and optional caching."""
        self.provider_name = "base"  # Override in subclasses
        self.cache_service = cache_service
        self.tenant_id = tenant_id
        self.cache_ttl_hours = 24  # Default cache TTL
        self.model = model_name  # Model name to be used by the service
        self.default_temperature = default_temperature  # Default temperature

    def _create_token_usage(
            self,
            prompt_tokens: int,
            completion_tokens: int,
            operation_tag: str,
            total_cost: float = 0.0
    ) -> TokenUsage:
        """Create token usage object."""
        return TokenUsage(
            operation_tag=operation_tag,
            prompt_tokens=prompt_tokens,
            completion_tokens=completion_tokens,
            total_tokens=prompt_tokens + completion_tokens,
            total_cost_in_usd=total_cost,
            provider=self.provider_name
        )

    @abstractmethod
    async def _generate_content_without_cache(
            self,
            prompt: str,
            is_json: bool = True,
            operation_tag: str = "default",
            temperature: Optional[float] = None
    ) -> Tuple[Union[Dict[str, Any], str], TokenUsage]:
        """Generate content from prompt without using cache."""
        pass

    async def generate_content(
            self,
            prompt: str,
            is_json: bool = True,
            operation_tag: str = "default",
            force_refresh: bool = False,
            temperature: Optional[float] = None
    ) -> Union[Dict[str, Any], str]:
        """Generate content from prompt, using cache if available."""
        # Use provided temperature or fall back to default
        used_temperature = temperature if temperature is not None else self.default_temperature

        if self.cache_service and not force_refresh:
            cached_response = None
            try:
                cached_response = await self.cache_service.get_cached_response(
                    prompt=prompt,
                    provider=self.provider_name,
                    model=self.model,
                    is_json=is_json,
                    operation_tag=operation_tag,
                    tenant_id=self.tenant_id,
                    temperature=used_temperature
                )
            except Exception as e:
                logger.error(f"Cache read failed: {e}")
                cached_response = None

            if cached_response:
                return cached_response["content"]

        response, token_usage = await self._generate_content_without_cache(
            prompt=prompt,
            is_json=is_json,
            operation_tag=operation_tag,
            temperature=used_temperature
        )

        if self.cache_service:
            try:
                await self.cache_service.cache_response(
                    prompt=prompt,
                    response=response,
                    token_usage=token_usage,
                    provider=self.provider_name,
                    model=self.model,
                    is_json=is_json,
                    operation_tag=operation_tag,
                    tenant_id=self.tenant_id,
                    ttl_hours=self.cache_ttl_hours,
                    temperature=used_temperature
                )
            except Exception as e:
                logger.error(f"Failed to cache response: {e}")

        return response

    @abstractmethod
    async def generate_search_content(
            self,
            prompt: str,
            search_context_size: str = "medium",
            user_location: Optional[Dict[str, Any]] = None,
            operation_tag: str = "search",
            force_refresh: bool = False
    ) -> Dict[str, Any]:
        """Generate content with web search capability.

        Args:
            prompt: The input prompt for the model
            search_context_size: Amount of search context to include ('low', 'medium', 'high')
            user_location: Optional location information for geographically relevant searches
            operation_tag: Identifier for the operation (used for token tracking)
            force_refresh: Whether to bypass cache

        Returns:
            Generated content with web search results
        """
        pass

    @abstractmethod
    async def generate_structured_search_content(
            self,
            prompt: str,
            response_schema: Any,  # Pydantic model class
            search_context_size: str = "medium",
            user_location: Optional[Dict[str, Any]] = None,
            operation_tag: str = "structured_search",
            force_refresh: bool = False
    ) -> Dict[str, Any]:
        """Generate content with web search capability and structured output format.

        Args:
            prompt: The input prompt for the model
            response_schema: Pydantic model class defining the response schema
            search_context_size: Amount of search context to include ('low', 'medium', 'high')
            user_location: Optional location information for geographically relevant searches
            operation_tag: Identifier for the operation (used for token tracking)
            force_refresh: Whether to bypass cache

        Returns:
            Generated content with web search results conforming to the schema
        """
        pass

class GeminiService(AIService):
    """Gemini implementation of AI service."""

    def __init__(
            self,
            model_name: Optional[str] = None,
            cache_service: Optional[AICacheService] = None,
            tenant_id: Optional[str] = None,
            default_temperature: Optional[float] = 0.0  # Default to 0.0 for deterministic outputs
    ):
        """Initialize Gemini client."""
        super().__init__(
            model_name=model_name,
            cache_service=cache_service,
            tenant_id=tenant_id,
            default_temperature=default_temperature
        )
        self.provider_name = "gemini"

        api_key = os.getenv("GEMINI_API_TOKEN")
        if not api_key:
            raise ValueError("GEMINI_API_TOKEN environment variable required")

        genai.configure(api_key=api_key)
        self.model = model_name or 'gemini-2.0-flash'
        self.model_instance = genai.GenerativeModel(self.model)

        # Approximate token count for cost estimation
        self.avg_chars_per_token = 4
        self.cost_per_1k_tokens = 0.00015  # Example rate

    @with_retry(retry_config=GEMINI_RETRY_CONFIG, operation_name="_gemini_generate_content")
    async def _generate_content_without_cache(
            self,
            prompt: str,
            is_json: bool = True,
            operation_tag: str = "default",
            temperature: Optional[float] = None
    ) -> Tuple[Union[Dict[str, Any], str], TokenUsage]:
        """Generate content using Gemini without using cache."""
        try:
            if is_json:
                prompt = f"{prompt}\n\nRespond in JSON format only."

            # Use provided temperature or default
            used_temperature = temperature if temperature is not None else self.default_temperature

            # Gemini's generate_content is synchronous, so we run it in a thread
            response = await self._generate_content_in_thread(prompt, used_temperature)

            if not response or not response.parts:
                logger.warning("Empty response from Gemini")
                token_usage = self._create_token_usage(0, 0, operation_tag)
                return {} if is_json else "", token_usage

            response_text = response.parts[0].text
            logger.debug(f"Gemini response: {response_text}")

            # Estimate token usage based on character count
            prompt_tokens = len(prompt) // self.avg_chars_per_token
            completion_tokens = len(response_text) // self.avg_chars_per_token
            total_tokens = prompt_tokens + completion_tokens
            total_cost = (total_tokens / 1000) * self.cost_per_1k_tokens

            token_usage = self._create_token_usage(
                prompt_tokens=prompt_tokens,
                completion_tokens=completion_tokens,
                operation_tag=operation_tag,
                total_cost=total_cost
            )

            if is_json:
                result = await self._parse_json_response_async(response_text)
                return result, token_usage
            return response_text, token_usage

        except Exception as e:
            logger.error(f"Error generating content with Gemini: {str(e)}")
            token_usage = self._create_token_usage(0, 0, operation_tag)
            return {} if is_json else "", token_usage

    @to_thread
    def _generate_content_in_thread(self, prompt: str, temperature: Optional[float] = None):
        """Run Gemini's synchronous generate_content in a separate thread"""
        generation_config = {}
        if temperature is not None:
            generation_config['temperature'] = temperature

        return self.model_instance.generate_content(
            prompt,
            generation_config=generation_config
        )

    @to_cpu_thread
    def _parse_json_response_async(self, response: str) -> Dict[str, Any]:
        """Parse JSON from Gemini response asynchronously."""
        # Since JSON parsing is CPU-bound rather than I/O-bound, we run it in a thread
        # to avoid blocking the event loop for complex or large JSON payloads
        return self._parse_json_response(response)

    def _parse_json_response(self, response: str) -> Dict[str, Any]:
        """Parse JSON from Gemini response."""
        try:
            # Clean response text
            text = response.strip()
            if text.startswith("```json"):
                text = text[7:]
            if text.startswith("```"):
                text = text[3:]
            if text.endswith("```"):
                text = text[:-3]
            text = text.strip()

            return json.loads(text)

        except Exception as e:
            logger.error(f"Error parsing JSON response: {str(e)}")
            return {}


    def generate_search_content(
            self,
            prompt: str,
            search_context_size: str = "medium",
            user_location: Optional[Dict[str, Any]] = None,
            operation_tag: str = "search",
            force_refresh: bool = False
    ) -> Dict[str, Any]:
        raise NotImplementedError("Generate search content is not implemented yet for Gemini AI Service")

    def generate_structured_search_content(
            self,
            prompt: str,
            response_schema: Any,  # Pydantic model class
            search_context_size: str = "medium",
            user_location: Optional[Dict[str, Any]] = None,
            operation_tag: str = "structured_search",
            force_refresh: bool = False
    ) -> Dict[str, Any]:
        raise NotImplementedError("Generate structured search content is not implemented yet for Gemini AI Service")


class OpenAIService(AIService):
    """OpenAI implementation of AI service."""

    def __init__(
            self,
            model_name: Optional[str] = None,
            cache_service: Optional[AICacheService] = None,
            tenant_id: Optional[str] = None,
            default_temperature: Optional[float] = 0.0  # Default to 0.0 for deterministic outputs
    ):
        """Initialize OpenAI client."""
        super().__init__(
            model_name=model_name,
            cache_service=cache_service,
            tenant_id=tenant_id,
            default_temperature=default_temperature
        )
        self.provider_name = "openai"

        api_key = os.getenv("OPENAI_API_KEY")
        if not api_key:
            raise ValueError("OPENAI_API_KEY environment variable required")

        self.client = AsyncOpenAI(api_key=api_key)
        self.model = model_name or "gpt-4o-mini"

        # OpenAI pricing per 1K tokens (can be configured)
        self.price_per_1k_tokens = {
            "gpt-4o-mini": {
                "input": 0.01,
                "output": 0.03
            },
            "gpt-4o": {
                "input": 0.1,
                "output": 0.3
            }
        }

    @with_retry(retry_config=OPENAI_RETRY_CONFIG, operation_name="_openai_generate_content")
    async def _generate_content_without_cache(
            self,
            prompt: str,
            is_json: bool = True,
            operation_tag: str = "default",
            temperature: Optional[float] = None
    ) -> Tuple[Union[Dict[str, Any], str], TokenUsage]:
        """Generate content using OpenAI without using cache."""
        try:
            messages = [
                {"role": "user", "content": prompt}
            ]

            # Add system message for JSON responses
            if is_json:
                messages.insert(0, {
                    "role": "system",
                    "content": "You are a helpful assistant that responds only in valid JSON format."
                })

            # Configure response format for JSON if needed
            response_format = {"type": "json_object"} if is_json else None

            # Use provided temperature or default
            used_temperature = temperature if temperature is not None else self.default_temperature

            response = await self.client.chat.completions.create(
                model=self.model,
                messages=messages,
                response_format=response_format,
                temperature=used_temperature
            )
            logger.debug(f"OpenAI response: {response}")

            if not response.choices:
                logger.warning("Empty response from OpenAI")
                token_usage = self._create_token_usage(0, 0, operation_tag)
                return {} if is_json else "", token_usage

            # Calculate cost
            prompt_cost = (response.usage.prompt_tokens / 1000) * self.price_per_1k_tokens[self.model]["input"]
            completion_cost = (response.usage.completion_tokens / 1000) * self.price_per_1k_tokens[self.model]["output"]
            total_cost = prompt_cost + completion_cost

            # Track token usage
            token_usage = TokenUsage(
                operation_tag=operation_tag,
                prompt_tokens=response.usage.prompt_tokens,
                completion_tokens=response.usage.completion_tokens,
                total_tokens=response.usage.total_tokens,
                total_cost_in_usd=total_cost,
                provider=self.provider_name
            )

            content = response.choices[0].message.content

            # Parse JSON response if needed
            if is_json:
                # JSON parsing can be CPU-intensive for large responses, so we run it in a thread
                result = await run_in_thread(json.loads, content, pool_type="cpu")
                return result, token_usage

            return content, token_usage

        except Exception as e:
            logger.error(f"Error generating content with OpenAI: {str(e)}")
            token_usage = self._create_token_usage(0, 0, operation_tag)
            return {} if is_json else "", token_usage

    # Helper methods for both search functions

    def _create_search_tool(
            self,
            search_context_size: str = "medium",
            user_location: Optional[Dict[str, Any]] = None
    ) -> Dict[str, Any]:
        """Create a search tool configuration object."""
        # Validate search_context_size
        if search_context_size not in ["low", "medium", "high"]:
            logger.warning(f"Invalid search_context_size: {search_context_size}, defaulting to 'medium'")
            search_context_size = "medium"

        # Configure search tool
        search_tool = {"type": "web_search_preview", "search_context_size": search_context_size}

        # Add user location if provided
        if user_location:
            search_tool["user_location"] = {"type": "approximate", **user_location}

        return search_tool

    def _generate_search_cache_key(
            self,
            prompt: str,
            search_context_size: str,
            operation_tag: str,
            user_location: Optional[Dict[str, Any]] = None,
            schema_info: Optional[str] = None
    ) -> str:
        """Generate a cache key for search operations."""
        cache_data = {
            'prompt': prompt,
            'provider': self.provider_name,
            'model': self.model,
            'search_context_size': search_context_size,
            'operation_tag': operation_tag,
            'schema_info': schema_info
        }

        # Add user location to cache key if provided
        if user_location:
            cache_data['user_location'] = json.dumps(user_location, sort_keys=True)

        # Generate cache key
        return hashlib.sha256(json.dumps(cache_data, sort_keys=True).encode()).hexdigest()

    async def _check_search_cache(
            self,
            cache_key: str,
            operation_tag: str
    ) -> Optional[Dict[str, Any]]:
        """Check if there's a cached response for the given cache key."""
        if not self.cache_service:
            return None

        try:
            query = f"""
            SELECT 
                response_data,
                prompt_tokens,
                completion_tokens,
                total_tokens,
                total_cost_in_usd
            FROM `{self.cache_service.project_id}.{self.cache_service.dataset}.{self.cache_service.table_name}`
            WHERE cache_key = @cache_key
            AND provider = @provider
            AND (expires_at IS NULL OR expires_at > CURRENT_TIMESTAMP())
            AND (tenant_id IS NULL OR tenant_id = @tenant_id)
            ORDER BY created_at DESC
            LIMIT 1
            """

            job_config = bigquery.QueryJobConfig(
                query_parameters=[
                    bigquery.ScalarQueryParameter("cache_key", "STRING", cache_key),
                    bigquery.ScalarQueryParameter("provider", "STRING", self.provider_name),
                    bigquery.ScalarQueryParameter("tenant_id", "STRING", self.tenant_id)
                ]
            )

            results = None # await self.cache_service._execute_query(query, job_config)

            if results:
                row = results[0]
                logger.info(f"Cache hit for search query with key: {cache_key[:8]}...")
                return row.response_data

        except Exception as e:
            logger.error(f"Cache read failed: {e}")

        return None

    async def _store_search_result(
            self,
            cache_key: str,
            result: Dict[str, Any],
            token_usage: TokenUsage,
            prompt: str
    ) -> None:
        """Store a search result in cache."""
        if not self.cache_service:
            return

        try:
            # Prepare expiration time
            expires_at = None
            if self.cache_ttl_hours is not None:
                expires_at = datetime.now(timezone.utc) + timedelta(hours=self.cache_ttl_hours)

            # Prepare row for insertion
            row = {
                "cache_key": cache_key,
                "provider": self.provider_name,
                "model": self.model,
                "prompt": prompt,
                "is_json_response": True,
                "operation_tag": token_usage.operation_tag,
                "response_data": json.dumps(result),
                "response_text": None,
                "prompt_tokens": token_usage.prompt_tokens,
                "completion_tokens": token_usage.completion_tokens,
                "total_tokens": token_usage.total_tokens,
                "total_cost_in_usd": token_usage.total_cost_in_usd,
                "created_at": datetime.now(timezone.utc).isoformat(),
                "expires_at": expires_at.isoformat() if expires_at else None,
                "tenant_id": self.tenant_id
            }

            # Insert row
            errors = await self.cache_service._insert_row(row)

            if errors:
                logger.error(f"Error caching search response: {errors}")

        except Exception as e:
            logger.error(f"Failed to cache search response: {e}")

    def _extract_json_from_text(self, text: str) -> Dict[str, Any]:
        """Extract JSON content from text response."""
        try:
            # Strategy 1: Find JSON between braces
            json_start = text.find('{')
            json_end = text.rfind('}') + 1
            if json_start >= 0 and json_end > json_start:
                return json.loads(text[json_start:json_end])

            # Strategy 2: Parse the whole text
            return json.loads(text)
        except json.JSONDecodeError:
            try:
                # Strategy 3: Use regex to find JSON pattern
                import re
                match = re.search(r'(\{[\s\S]*\})', text)
                if match:
                    return json.loads(match.group(1))
            except (json.JSONDecodeError, AttributeError):
                pass

            # Fallback: Return the text in a structured format
            logger.warning(f"Failed to parse JSON from response: {text[:100]}...")
            return {"text": text, "error": "Failed to parse as JSON"}

    def _extract_citations(self, response) -> List[Dict[str, Any]]:
        """Extract citation information from response."""
        citations = []
        try:
            for message in response.messages:
                if message.role == "assistant" and hasattr(message, "content"):
                    for content_item in message.content:
                        if hasattr(content_item, "annotations"):
                            for annotation in content_item.annotations:
                                if annotation.type == "url_citation":
                                    citations.append({
                                        "url": annotation.url,
                                        "title": annotation.title,
                                        "start_index": annotation.start_index,
                                        "end_index": annotation.end_index
                                    })
        except Exception as e:
            logger.error(f"Error extracting citations: {str(e)}")

        return citations

    def _estimate_search_token_usage(
            self,
            prompt: str,
            output: str,
            search_context_size: str,
            operation_tag: str
    ) -> TokenUsage:
        """Estimate token usage and cost for search operations."""
        # Rough token estimation
        prompt_tokens = len(prompt) // 4 or 1
        completion_tokens = len(output) // 4 or 1
        total_tokens = prompt_tokens + completion_tokens

        # Cost calculation
        input_price = self.price_per_1k_tokens.get(self.model, {}).get("input", 0.01)
        output_price = self.price_per_1k_tokens.get(self.model, {}).get("output", 0.03)
        search_multiplier = {"low": 1.0, "medium": 2.0, "high": 3.0}[search_context_size]

        prompt_cost = (prompt_tokens / 1000) * input_price
        completion_cost = (completion_tokens / 1000) * output_price
        search_cost = (total_tokens / 1000) * 0.01 * search_multiplier
        total_cost = prompt_cost + completion_cost + search_cost

        return TokenUsage(
            operation_tag=operation_tag,
            prompt_tokens=prompt_tokens,
            completion_tokens=completion_tokens,
            total_tokens=total_tokens,
            total_cost_in_usd=total_cost,
            provider=self.provider_name
        )


    async def _execute_search_request(
            self,
            prompt: str,
            search_tool: Dict[str, Any],
            response_schema: Optional[Any] = None,
            operation_tag: str = "search"
    ) -> Tuple[Dict[str, Any], TokenUsage]:
        """
        Execute a search API request to OpenAI.

        Args:
            prompt: The input prompt
            search_tool: Configured search tool
            response_schema: Optional response schema for structured outputs
            operation_tag: Operation identifier for token tracking

        Returns:
            Tuple of (result, token_usage)
        """
        try:
            # For structured outputs, prepare schema information
            schema_description = ""

            if response_schema and hasattr(response_schema, "model_fields"):
                # Since the prompt already contains schema info, we'll only add minimal guidance
                schema_description = "Make sure your response follows the exact schema structure specified in the prompt."

            # For structured outputs, we want to use the prompt directly without adding extra system messages
            # that might conflict with the schema already in the prompt
            if response_schema:
                # The prompt already contains the schema and format instructions
                enhanced_prompt = prompt
            else:
                # For non-structured requests, add JSON formatting instruction
                system_message = "You are a helpful assistant that provides accurate information based on web search results. Format your response as valid JSON."
                enhanced_prompt = f"{system_message}\n\n{prompt}"

            # Use the responses API - web search doesn't support parse method
            response = await self.client.responses.create(
                model=self.model,
                tools=[search_tool],
                input=enhanced_prompt,
                temperature=self.default_temperature
            )

            # Extract the output text
            output_content = response.output_text

            # Parse the JSON response
            result = self._extract_json_from_text(output_content)

            # If we have a schema, validate the response structure
            if response_schema and hasattr(response_schema, "model_fields"):
                # Check if required fields exist, add empty arrays if missing
                for field_name in response_schema.model_fields:
                    if field_name not in result:
                        field_type = str(response_schema.model_fields[field_name].annotation)
                        # If it's a list type, add an empty list
                        if "List" in field_type:
                            result[field_name] = []

            # Extract citations if available
            citations = self._extract_citations(response)
            if citations:
                result["citations"] = citations

            # Estimate token usage
            token_usage = self._estimate_search_token_usage(
                prompt=prompt,
                output=output_content,
                search_context_size=search_tool["search_context_size"],
                operation_tag=operation_tag
            )

            return result, token_usage

        except Exception as e:
            logger.error(f"Error in search request: {str(e)}", exc_info=True)
            error_result = {"error": str(e)}

            # Create minimal token usage for error case
            token_usage = TokenUsage(
                operation_tag=operation_tag,
                prompt_tokens=len(prompt) // 4 or 1,
                completion_tokens=10,  # Minimal value for error
                total_tokens=(len(prompt) // 4 or 1) + 10,
                total_cost_in_usd=0.001,  # Minimal cost for tracking
                provider=self.provider_name
            )

            return error_result, token_usage

    async def generate_search_content(
            self,
            prompt: str,
            search_context_size: str = "medium",
            user_location: Optional[Dict[str, Any]] = None,
            operation_tag: str = "search",
            force_refresh: bool = False
    ) -> Dict[str, Any]:
        """Generate content with web search capability."""
        search_tool = self._create_search_tool(search_context_size, user_location)

        cache_key = self._generate_search_cache_key(
            prompt=prompt,
            search_context_size=search_context_size,
            operation_tag=operation_tag,
            user_location=user_location
        )

        if not force_refresh:
            cached_result = await self._check_search_cache(cache_key, operation_tag)
            if cached_result:
                return cached_result

        result, token_usage = await self._execute_search_request(
            prompt=prompt,
            search_tool=search_tool,
            operation_tag=operation_tag
        )

        await self._store_search_result(
            cache_key=cache_key,
            result=result,
            token_usage=token_usage,
            prompt=prompt
        )

        return result

    async def generate_structured_search_content(
            self,
            prompt: str,
            response_schema: Any,  # Pydantic model class
            search_context_size: str = "medium",
            user_location: Optional[Dict[str, Any]] = None,
            operation_tag: str = "structured_search",
            force_refresh: bool = False
    ) -> Dict[str, Any]:
        """Generate content with web search capability and structured output format."""
        # Create search tool
        search_tool = self._create_search_tool(search_context_size, user_location)

        # Create schema_info for cache key
        schema_info = str(response_schema) if response_schema else None

        # Generate cache key
        cache_key = self._generate_search_cache_key(
            prompt=prompt,
            search_context_size=search_context_size,
            operation_tag=operation_tag,
            user_location=user_location,
            schema_info=schema_info
        )

        # Check cache if not forcing refresh
        if not force_refresh:
            cached_result = await self._check_search_cache(cache_key, operation_tag)
            if cached_result:
                return cached_result

        # Execute search request with schema
        result, token_usage = await self._execute_search_request(
            prompt=prompt,
            search_tool=search_tool,
            response_schema=response_schema,
            operation_tag=operation_tag
        )

        # Handle refusals if present
        if "refusal" in result or "error" in result:
            empty_response = {field: [] for field in response_schema.model_fields.keys()}
            if "refusal" in result:
                logger.warning(f"Model refused to respond: {result['refusal']}")
                empty_response["_refusal_message"] = result["refusal"]
            elif "error" in result:
                logger.warning(f"Error in response: {result['error']}")
                empty_response["_refusal_message"] = result["error"]
            # Provide a minimal valid response structure
            if hasattr(response_schema, "model_fields"):
                result = empty_response

        else:
            # Store result in cache
            await self._store_search_result(
                cache_key=cache_key,
                result=result,
                token_usage=token_usage,
                prompt=prompt
            )

        # Try to validate and convert the result using the schema
        if hasattr(response_schema, "model_validate"):
            try:
                # This will raise an exception if the result doesn't match the schema
                validated_model = response_schema.model_validate(result)
                # Convert back to dict for consistency
                if hasattr(validated_model, "model_dump"):
                    result = validated_model.model_dump()
            except Exception as e:
                logger.warning(f"Schema validation failed: {str(e)}. Using unvalidated result.")

        return result

class AIServiceFactory:
    """Factory for creating AI service instances with integrated caching."""

    def __init__(
            self
    ):
        """
        Initialize the factory with optional BigQuery settings for caching.

        If caching is enabled, will use:
        - GOOGLE_CLOUD_PROJECT env var if project_id not provided
        - BIGQUERY_DATASET env var (default: 'userport_enrichment') if dataset not provided
        """
        self.cache_service = None

        # Get project ID from args or environment
        self.project_id = os.getenv('GOOGLE_CLOUD_PROJECT')
        if not self.project_id:
            raise ValueError("Project ID must be provided or GOOGLE_CLOUD_PROJECT environment variable must be set")

        # Get dataset from args or environment
        self.dataset = os.getenv('BIGQUERY_DATASET', 'userport_enrichment')

        # Initialize BigQuery client
        try:
            bigquery_client = bigquery.Client(project=self.project_id)
            self.cache_service = AICacheService(
                client=bigquery_client,
                project_id=self.project_id,
                dataset=self.dataset
            )
        except Exception as e:
            logger.error(f"Failed to initialize BigQuery client: {str(e)}")
            raise

    def create_service(
            self,
            provider: str = "openai",
            tenant_id: Optional[str] = None,
            model_name: Optional[str] = None,
            cache_ttl_hours: Optional[int] = 24,
            default_temperature: Optional[float] = 0.2
    ) -> AIService:
        """
        Create an AI service instance with optional caching.

        Args:
            provider: AI provider ("openai" or "gemini")
            model_name: Optional model name to use
            tenant_id: Optional tenant ID for multi-tenancy
            cache_ttl_hours: Cache TTL in hours (only used if caching is enabled)
            default_temperature: Default temperature setting (0.0 for deterministic outputs)

        Returns:
            AIService instance (OpenAIService or GeminiService)
        """
        service: AIService

        if provider.lower() == "openai":
            service = OpenAIService(
                model_name=model_name,
                cache_service=self.cache_service,
                tenant_id=tenant_id,
                default_temperature=default_temperature
            )
        elif provider.lower() == "gemini":
            service = GeminiService(
                model_name=model_name,
                cache_service=self.cache_service,
                tenant_id=tenant_id,
                default_temperature=default_temperature
            )
        else:
            raise ValueError(f"Unsupported AI provider: {provider}")

        # Set cache TTL if caching is enabled
        if self.cache_service and cache_ttl_hours is not None:
            service.cache_ttl_hours = cache_ttl_hours

        return service

    async def close(self):
        """Close any resources used by the factory."""
        pass  # Add any cleanup code here if needed in the future