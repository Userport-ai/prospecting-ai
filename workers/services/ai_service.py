import asyncio
import hashlib
import json
import logging
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

logger = logging.getLogger(__name__)

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
            operation_tag: str
    ) -> str:
        """Generate a unique cache key for the AI request."""
        cache_data = {
            'prompt': prompt,
            'provider': provider,
            'model': model,
            'is_json': is_json,
            'operation_tag': operation_tag
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
            tenant_id: Optional[str] = None
    ) -> Optional[Dict[str, Any]]:
        """Get cached response for the given AI prompt."""
        cache_key = self._generate_cache_key(prompt, provider, model, is_json, operation_tag)

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
                bigquery.ScalarQueryParameter("tenant_id", "STRING", tenant_id)
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
            ttl_hours: Optional[int] = None
    ) -> None:
        """Cache an AI response."""
        cache_key = self._generate_cache_key(prompt, provider, model, is_json, operation_tag)
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
            tenant_id: Optional[str] = None
    ):
        """Initialize service with token tracking and optional caching."""
        self.provider_name = "base"  # Override in subclasses
        self.cache_service = cache_service
        self.tenant_id = tenant_id
        self.cache_ttl_hours = 24  # Default cache TTL
        self.model = model_name  # Model name to be used by the service

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
            operation_tag: str = "default"
    ) -> Tuple[Union[Dict[str, Any], str], TokenUsage]:
        """Generate content from prompt without using cache."""
        pass

    async def generate_content(
            self,
            prompt: str,
            is_json: bool = True,
            operation_tag: str = "default",
            force_refresh: bool = False
    ) -> Union[Dict[str, Any], str]:
        """Generate content from prompt, using cache if available."""
        if self.cache_service and not force_refresh:
            cached_response = None
            try:
                cached_response = await self.cache_service.get_cached_response(
                    prompt=prompt,
                    provider=self.provider_name,
                    model=self.model,
                    is_json=is_json,
                    operation_tag=operation_tag,
                    tenant_id=self.tenant_id
                )
            except Exception as e:
                logger.error(f"Cache read failed: {e}")
                cached_response = None

            if cached_response:
                return cached_response["content"]

        response, token_usage = await self._generate_content_without_cache(
            prompt=prompt,
            is_json=is_json,
            operation_tag=operation_tag
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
                    ttl_hours=self.cache_ttl_hours
                )
            except Exception as e:
                logger.error(f"Failed to cache response: {e}")

        return response

class GeminiService(AIService):
    """Gemini implementation of AI service."""

    def __init__(
            self,
            model_name: Optional[str] = None,
            cache_service: Optional[AICacheService] = None,
            tenant_id: Optional[str] = None
    ):
        """Initialize Gemini client."""
        super().__init__(model_name=model_name, cache_service=cache_service, tenant_id=tenant_id)
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
            operation_tag: str = "default"
    ) -> Tuple[Union[Dict[str, Any], str], TokenUsage]:
        """Generate content using Gemini without using cache."""
        try:
            if is_json:
                prompt = f"{prompt}\n\nRespond in JSON format only."

            # Gemini's generate_content is synchronous, so we run it in a thread
            response = await self._generate_content_in_thread(prompt)

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
    def _generate_content_in_thread(self, prompt: str):
        """Run Gemini's synchronous generate_content in a separate thread"""
        return self.model_instance.generate_content(prompt)

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


class OpenAIService(AIService):
    """OpenAI implementation of AI service."""

    def __init__(
            self,
            model_name: Optional[str] = None,
            cache_service: Optional[AICacheService] = None,
            tenant_id: Optional[str] = None
    ):
        """Initialize OpenAI client."""
        super().__init__(model_name=model_name, cache_service=cache_service, tenant_id=tenant_id)
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
            operation_tag: str = "default"
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

            response = await self.client.chat.completions.create(
                model=self.model,
                messages=messages,
                response_format=response_format
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
            cache_ttl_hours: Optional[int] = 24
    ) -> AIService:
        """
        Create an AI service instance with optional caching.

        Args:
            provider: AI provider ("openai" or "gemini")
            model_name: Optional model name to use
            tenant_id: Optional tenant ID for multi-tenancy
            cache_ttl_hours: Cache TTL in hours (only used if caching is enabled)

        Returns:
            AIService instance (OpenAIService or GeminiService)
        """
        service: AIService

        if provider.lower() == "openai":
            service = OpenAIService(
                model_name=model_name,
                cache_service=self.cache_service,
                tenant_id=tenant_id
            )
        elif provider.lower() == "gemini":
            service = GeminiService(
                model_name=model_name,
                cache_service=self.cache_service,
                tenant_id=tenant_id
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