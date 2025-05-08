import enum
import hashlib
import json
from abc import ABC, abstractmethod
from datetime import datetime, timedelta, timezone
from typing import Dict, Any, Optional, Union, Tuple

from google.cloud import bigquery

from utils.token_usage import TokenUsage
from utils.loguru_setup import logger
from services.ai.ai_cache_service import AICacheService
from json_repair import loads as repair_loads


class ThinkingBudget(enum.Enum):
    """Enum for thinking budget levels."""
    ZERO = 0
    LOW = 1024
    MEDIUM = 8192
    HIGH = 24576

SUPPORTED_MODELS = {
    # OpenAI models
    "gpt-4.1": "openai",
    "gpt-4.1-mini": "openai",
    "gpt-4.1-nano": "openai",
    "gpt-4o": "openai",
    "gpt-4o-mini": "openai",

    # Google Gemini models
    "gemini-2.5-flash-preview-04-17": "gemini",
    "gemini-2.5-pro-preview-03-25": "gemini",
    "gemini-2.0-flash": "gemini",
}

SUPPORTED_MODEL_NAMES = list(SUPPORTED_MODELS.keys())


class AIService(ABC):
    """Abstract base class for AI service providers."""

    def __init__(
            self,
            model_name: Optional[str] = None,
            cache_service: Optional[AICacheService] = None,
            tenant_id: Optional[str] = None,
            default_temperature: Optional[float] = None,
            thinking_budget: Optional[ThinkingBudget] = None
    ):
        if model_name and not self.is_supported_model(model_name):
            raise ValueError(f"Model {model_name} is not supported by this service.")

        """Initialize service with token tracking and optional caching."""
        self.provider_name = "base"  # Override in subclasses
        self.cache_service = cache_service
        self.tenant_id = tenant_id
        self.cache_ttl_hours = 24  # Default cache TTL
        self.model = model_name  # Model name to be used by the service
        self.default_temperature = default_temperature  # Default temperature
        self.thinking_budget = thinking_budget  # Thinking budget parameter

    # ===============================
    # Core Content Generation Methods
    # ===============================

    @staticmethod
    def is_supported_model(name: str) -> bool:
        """
        Returns True if `name` is one of the supported model identifiers.
        """
        return name and name in SUPPORTED_MODEL_NAMES

    @staticmethod
    def get_modelprovider(name: str) -> Optional[str]:
        return SUPPORTED_MODELS.get(name, None)

    @abstractmethod
    async def _generate_content_without_cache(
            self,
            prompt: str,
            is_json: bool = True,
            operation_tag: str = "default",
            temperature: Optional[float] = None,
            thinking_budget: Optional[ThinkingBudget] = None,
            system_prompt: Optional[str] = None,
            user_prompt: Optional[str] = None
    ) -> Tuple[Union[Dict[str, Any], str], TokenUsage]:
        """Generate content from prompt without using cache.
        
        If system_prompt and user_prompt are provided, the prompt parameter is ignored and 
        the LLM-specific implementation should handle formatting these appropriately for the model.
        """
        pass

    async def generate_content(
            self,
            prompt: str = None,
            is_json: bool = True,
            operation_tag: str = "default",
            force_refresh: bool = False,
            temperature: Optional[float] = None,
            thinking_budget: Optional[ThinkingBudget] = None,
            system_prompt: Optional[str] = None,
            user_prompt: Optional[str] = None
    ) -> Union[Dict[str, Any], str]:
        """Generate content from prompt, using cache if available.
        
        This method now supports two ways of providing prompts:
        1. Legacy mode: Pass a single combined prompt in the 'prompt' parameter
        2. Structured mode: Pass separate system_prompt and user_prompt parameters
        
        If both methods are used, structured mode takes precedence.
        """
        # Use provided temperature or fall back to default
        used_temperature = temperature if temperature is not None else self.default_temperature
        
        # Generate a combined prompt for caching purposes if using separate prompts
        cache_prompt = prompt
        if system_prompt is not None or user_prompt is not None:
            # Create a deterministic combined prompt for cache key generation
            system_part = system_prompt or ""
            user_part = user_prompt or ""
            cache_prompt = f"<system>\n{system_part}\n</system>\n\n<user>\n{user_part}\n</user>"
        
        # Ensure we have at least one form of prompt
        if cache_prompt is None:
            raise ValueError("Either 'prompt' or at least one of 'system_prompt'/'user_prompt' must be provided")

        if self.cache_service and not force_refresh:
            cached_response = None
            try:
                cached_response = await self.cache_service.get_cached_response(
                    prompt=cache_prompt,
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

        try:
            response, token_usage = await self._generate_content_without_cache(
                prompt=prompt,
                is_json=is_json,
                operation_tag=operation_tag,
                temperature=used_temperature,
                thinking_budget=thinking_budget,
                system_prompt=system_prompt,
                user_prompt=user_prompt
            )
        except ValueError as ve:
            logger.error(f"Got empty response while generating content: {ve}")
            return {} # Empty response

        if self.cache_service:
            try:
                await self.cache_service.cache_response(
                    prompt=cache_prompt,
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

    # ===============================
    # Search-based Content Generation
    # ===============================

    @abstractmethod
    async def _execute_search_request(
            self,
            prompt: str,
            search_context_size: str = "medium",
            user_location: Optional[Dict[str, Any]] = None,
            response_schema: Optional[Any] = None,
            operation_tag: str = "search",
            temperature: Optional[float] = None,
            thinking_budget: Optional[ThinkingBudget] = None,
            system_prompt: Optional[str] = None,
            user_prompt: Optional[str] = None
    ) -> Tuple[Dict[str, Any], TokenUsage]:
        """Execute a search request specific to the provider.
        
        If system_prompt and user_prompt are provided, the prompt parameter is ignored and 
        the LLM-specific implementation should handle formatting these appropriately for the model.
        """
        pass

    async def generate_search_content(
            self,
            prompt: str = None,
            search_context_size: str = "medium",
            user_location: Optional[Dict[str, Any]] = None,
            operation_tag: str = "search",
            force_refresh: bool = True,
            temperature=0.1,
            thinking_budget: Optional[ThinkingBudget] = None,
            system_prompt: Optional[str] = None,
            user_prompt: Optional[str] = None
    ) -> Dict[str, Any]:
        """Generate content with web search capability.

        This is a generic implementation that subclasses can override if needed.
        
        This method now supports two ways of providing prompts:
        1. Legacy mode: Pass a single combined prompt in the 'prompt' parameter
        2. Structured mode: Pass separate system_prompt and user_prompt parameters
        
        If both methods are used, structured mode takes precedence.
        """
        # Generate a combined prompt for caching purposes if using separate prompts
        cache_prompt = prompt
        if system_prompt is not None or user_prompt is not None:
            # Create a deterministic combined prompt for cache key generation
            system_part = system_prompt or ""
            user_part = user_prompt or ""
            cache_prompt = f"<system>\n{system_part}\n</system>\n\n<user>\n{user_part}\n</user>"
        
        # Ensure we have at least one form of prompt
        if cache_prompt is None:
            raise ValueError("Either 'prompt' or at least one of 'system_prompt'/'user_prompt' must be provided")
            
        # Generate cache key
        cache_key = self._generate_search_cache_key(
            prompt=cache_prompt,
            search_context_size=search_context_size,
            operation_tag=operation_tag,
            user_location=user_location
        )

        # Check cache if not forcing refresh
        if not force_refresh and self.cache_service:
            cached_result = await self._check_search_cache(cache_key, operation_tag)
            if cached_result:
                return cached_result

        # Execute search request - implementation required in subclasses
        result, token_usage = await self._execute_search_request(
            prompt=prompt,
            search_context_size=search_context_size,
            user_location=user_location,
            operation_tag=operation_tag,
            temperature=temperature,
            thinking_budget=thinking_budget,
            system_prompt=system_prompt,
            user_prompt=user_prompt
        )

        # Store result in cache
        if self.cache_service:
            await self._store_search_result(
                cache_key=cache_key,
                result=result,
                token_usage=token_usage,
                prompt=cache_prompt
            )

        return result

    async def generate_structured_search_content(
            self,
            prompt: str = None,
            response_schema: Optional[Any] = None,  # Pydantic model class
            search_context_size: str = "medium",
            user_location: Optional[Dict[str, Any]] = None,
            operation_tag: str = "structured_search",
            force_refresh: bool = False,
            temperature=0.1,
            thinking_budget: Optional[ThinkingBudget] = None,
            system_prompt: Optional[str] = None,
            user_prompt: Optional[str] = None
    ) -> Dict[str, Any]:
        """Generate content with web search capability and structured output format.

        This is a generic implementation that subclasses can override if needed.
        
        This method now supports two ways of providing prompts:
        1. Legacy mode: Pass a single combined prompt in the 'prompt' parameter
        2. Structured mode: Pass separate system_prompt and user_prompt parameters
        
        If both methods are used, structured mode takes precedence.
        """
        # Generate a combined prompt for caching purposes if using separate prompts
        cache_prompt = prompt
        if system_prompt is not None or user_prompt is not None:
            # Create a deterministic combined prompt for cache key generation
            system_part = system_prompt or ""
            user_part = user_prompt or ""
            cache_prompt = f"<system>\n{system_part}\n</system>\n\n<user>\n{user_part}\n</user>"
        
        # Ensure we have at least one form of prompt
        if cache_prompt is None:
            raise ValueError("Either 'prompt' or at least one of 'system_prompt'/'user_prompt' must be provided")
            
        # Create schema_info for cache key
        schema_info = str(response_schema) if response_schema else None

        # Generate cache key
        cache_key = self._generate_search_cache_key(
            prompt=cache_prompt,
            search_context_size=search_context_size,
            operation_tag=operation_tag,
            user_location=user_location,
            schema_info=schema_info
        )

        # Check cache if not forcing refresh
        if not force_refresh and self.cache_service:
            cached_result = await self._check_search_cache(cache_key, operation_tag)
            if cached_result:
                return cached_result

        # Execute search request with schema - implementation required in subclasses
        result, token_usage = await self._execute_search_request(
            prompt=prompt,
            search_context_size=search_context_size,
            user_location=user_location,
            response_schema=response_schema,
            operation_tag=operation_tag,
            thinking_budget=thinking_budget,
            temperature=temperature,
            system_prompt=system_prompt,
            user_prompt=user_prompt
        )

        # Handle refusals if present
        if "refusal" in result or "error" in result:
            empty_response = {}
            if response_schema is not None and hasattr(response_schema, "model_fields"):
                empty_response = {field: [] if "List" in str(field_info.annotation) else None
                                  for field, field_info in response_schema.model_fields.items()}

            if "refusal" in result:
                logger.warning(f"Model refused to respond: {result['refusal']}")
                empty_response["_refusal_message"] = result["refusal"]
            elif "error" in result:
                logger.warning(f"Error in response: {result['error']}")
                empty_response["_error_message"] = result["error"]

            result = empty_response

        # Store result in cache
        if self.cache_service:
            await self._store_search_result(
                cache_key=cache_key,
                result=result,
                token_usage=token_usage,
                prompt=cache_prompt
            )

        # Try to validate and convert the result using the schema
        if response_schema is not None and hasattr(response_schema, "model_validate"):
            try:
                # This will raise an exception if the result doesn't match the schema
                validated_model = response_schema.model_validate(result)
                # Convert back to dict for consistency
                if hasattr(validated_model, "model_dump"):
                    result = validated_model.model_dump()
            except Exception as e:
                logger.warning(f"Schema validation failed: {str(e)}. Using unvalidated result.")

        return result

    # ===============================
    # Utility Methods
    # ===============================

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

    def _extract_json_from_text(self, text: str) -> Dict[str, Any]:
        """Extract JSON content from text response."""
        try:
            # Let json_repair handle everything - it returns Python objects directly
            return repair_loads(text)
        except Exception as e:
            logger.error(f"Error parsing JSON response: {str(e)}")
            return {}


    # ===============================
    # Cache-related Methods
    # ===============================

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

            # Execute query in a separate thread
            results = await self.cache_service._execute_query(query, job_config)

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
