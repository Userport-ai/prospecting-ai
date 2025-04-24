import os
from typing import Dict, Any, Optional, Union, Tuple

import google.genai as genai
from google.api_core.exceptions import ResourceExhausted as GoogleAPIResourceExhausted
from google.genai import types

from utils.async_utils import to_thread, to_cpu_thread
from utils.retry_utils import RetryableError, RetryConfig, with_retry
from utils.token_usage import TokenUsage
from utils.loguru_setup import logger
from services.ai_cache_service import AICacheService
from services.ai_service_base import AIService


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

        # Create client instead of configuring globally
        self.client = genai.Client(api_key=api_key)
        self.model = model_name or 'gemini-2.0-flash'

        # Approximate token count for cost estimation
        self.avg_chars_per_token = 4
        self.cost_per_1k_tokens = 0.00015  # Example rate

    # ===============================
    # Core Content Generation Methods
    # ===============================

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
            # Create config for the API call
            config_params = {}

            # Use provided temperature or default
            used_temperature = temperature if temperature is not None else self.default_temperature
            if used_temperature is not None:
                config_params['temperature'] = used_temperature

            if is_json:
                prompt = f"{prompt}\n\nRespond in JSON format only."
                config_params['response_mime_type'] = 'application/json'

            # Run in thread since we're using the synchronous API
            response = await self._generate_content_in_thread(prompt, config_params)

            if not response or not hasattr(response, 'text'):
                logger.warning("Empty response from Gemini")
                token_usage = self._create_token_usage(0, 0, operation_tag)
                return {} if is_json else "", token_usage

            response_text = response.text
            logger.debug(f"Gemini response: {response}")

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

    # ===============================
    # Search-based Content Generation
    # ===============================

    @with_retry(retry_config=GEMINI_RETRY_CONFIG, operation_name="_gemini_generate_search_content")
    async def _execute_search_request(
            self,
            prompt: str,
            search_context_size: str = "medium",
            user_location: Optional[Dict[str, Any]] = None,
            response_schema: Optional[Any] = None,
            operation_tag: str = "search"
    ) -> Tuple[Union[Dict[str, Any], str], TokenUsage]:
        """Execute search request using Gemini API."""
        try:
            # Prepare enhanced prompt based on schema if provided
            enhanced_prompt = prompt
            if response_schema and hasattr(response_schema, "model_fields"):
                schema_description = []
                for field_name, field_info in response_schema.model_fields.items():
                    field_type = str(field_info.annotation)
                    description = getattr(field_info, "description", "")
                    schema_description.append(f"- {field_name}: {field_type}{' - ' + description if description else ''}")

                enhanced_prompt = f"{prompt}\n\nRespond with JSON data in this structure:\n{chr(10).join(schema_description)}\n\nEnsure your response is valid JSON."
            else:
                enhanced_prompt = f"{prompt}\n\nRespond with valid JSON data."

            # Configure search parameters
            search_params = {}
            if user_location:
                search_params["user_location"] = user_location

            # Run in thread since we're using the synchronous API
            response = await self._generate_search_content_in_thread(
                prompt=enhanced_prompt,
                search_params=search_params,
                temperature=self.default_temperature
            )

            if not response or not hasattr(response, 'text'):
                logger.warning("Empty search response from Gemini")
                token_usage = self._create_token_usage(0, 0, operation_tag)
                return {} if response_schema else "", token_usage

            response_text = response.text
            logger.debug(f"Gemini search response: {response}...")

            # Estimate token usage with search multiplier
            multiplier = 1.0

            prompt_tokens = len(enhanced_prompt) // self.avg_chars_per_token
            prompt_tokens = int(prompt_tokens * multiplier)  # Account for search context
            completion_tokens = len(response_text) // self.avg_chars_per_token
            total_tokens = prompt_tokens + completion_tokens

            # Apply higher cost for search operations
            search_cost_multiplier = 1.2  # 20% premium for search operations
            total_cost = (total_tokens / 1000) * self.cost_per_1k_tokens * search_cost_multiplier

            token_usage = self._create_token_usage(
                prompt_tokens=prompt_tokens,
                completion_tokens=completion_tokens,
                operation_tag=operation_tag,
                total_cost=total_cost
            )

            # Parse JSON response if needed
            if response_schema or "json" in enhanced_prompt.lower():
                result = await self._parse_json_response_async(response_text)
                # Add metadata about the search
                result["_search_metadata"] = {
                    "provider": self.provider_name,
                    "model": self.model,
                    "search_context_size": search_context_size
                }
                return result, token_usage

            return response_text, token_usage

        except Exception as e:
            logger.error(f"Error in Gemini search request: {str(e)}", exc_info=True)
            error_result = {"error": str(e)}
            token_usage = self._create_token_usage(len(prompt) // 4, 10, operation_tag, 0.001)
            return error_result, token_usage

    # ===============================
    # Thread Execution Helpers
    # ===============================

    @to_thread
    def _generate_content_in_thread(self, prompt: str, config_params: Dict[str, Any]):
        """Run Gemini's synchronous generate_content in a separate thread"""
        # Create a GenerateContentConfig object from the config dictionary
        config = types.GenerateContentConfig(**config_params) if config_params else None

        return self.client.models.generate_content(
            model=self.model,
            contents=prompt,
            config=config
        )

    @to_thread
    def _generate_search_content_in_thread(self, prompt: str, search_params: Dict[str, Any], temperature: Optional[float] = None):
        """Execute Gemini's search-enabled content generation in a separate thread."""
        # Create the Google Search tool
        search_tool = types.Tool(google_search=types.GoogleSearch(**search_params))

        # Prepare generation config
        config_params = {}
        if temperature is not None:
            config_params['temperature'] = temperature

        return self.client.models.generate_content(
            model=self.model,
            contents=prompt,
            config=types.GenerateContentConfig(
                tools=[search_tool],
                **config_params
            )
        )

    # ===============================
    # Response Processing Helpers
    # ===============================

    @to_cpu_thread
    def _parse_json_response_async(self, response: str) -> Dict[str, Any]:
        """Parse JSON from Gemini response asynchronously."""
        # Since JSON parsing is CPU-bound rather than I/O-bound, we run it in a thread
        # to avoid blocking the event loop for complex or large JSON payloads
        return self._extract_json_from_text(response)