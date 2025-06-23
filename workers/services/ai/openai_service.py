import json
import os
from typing import Dict, Any, Optional, Union, Tuple, List

from openai import AsyncOpenAI

from utils.async_utils import run_in_thread
from utils.retry_utils import RetryConfig, with_retry
from utils.token_usage import TokenUsage
from utils.loguru_setup import logger
from services.ai.ai_cache_service import AICacheService
from services.ai.ai_service_base import AIService, ThinkingBudget

# Retry configurations
OPENAI_RETRY_CONFIG = RetryConfig(
    max_attempts=3,
    base_delay=2.0,
    max_delay=30.0,
    retryable_exceptions=[
        ValueError,
        RuntimeError,
        TimeoutError,
        ConnectionError
    ]
)


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

    # ===============================
    # Core Content Generation Methods
    # ===============================

    @with_retry(retry_config=OPENAI_RETRY_CONFIG, operation_name="_openai_generate_content")
    async def _generate_content_without_cache(
            self,
            prompt: str = None,
            is_json: bool = True,
            operation_tag: str = "default",
            temperature: Optional[float] = None,
            thinking_budget: Optional[ThinkingBudget] = None,
            system_prompt: Optional[str] = None,
            user_prompt: Optional[str] = None
    ) -> Tuple[Union[Dict[str, Any], str], TokenUsage]:
        """Generate content using OpenAI without using cache.
        
        This method now supports two ways of providing prompts:
        1. Legacy mode: Pass a single combined prompt in the 'prompt' parameter
        2. Structured mode: Pass separate system_prompt and user_prompt parameters
        
        If both methods are used, structured mode takes precedence.
        """
        try:
            # Determine which mode to use based on parameters
            if system_prompt is not None or user_prompt is not None:
                # Structured mode - build messages from system and user prompts
                messages = []
                
                # Add system message if provided or if we need JSON
                if system_prompt is not None:
                    messages.append({"role": "system", "content": system_prompt})
                elif is_json:
                    messages.append({
                        "role": "system",
                        "content": "You are a helpful assistant that responds only in valid JSON format."
                    })
                
                # Add user message if provided
                if user_prompt is not None:
                    messages.append({"role": "user", "content": user_prompt})
            else:
                # Legacy mode - use the prompt parameter
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

    # ===============================
    # Search-based Content Generation
    # ===============================

    async def _execute_search_request(
            self,
            prompt: str = None,
            search_context_size: str = "medium",
            user_location: Optional[Dict[str, Any]] = None,
            response_schema: Optional[Any] = None,
            operation_tag: str = "search",
            thinking_budget: Optional[ThinkingBudget] = None,
            system_prompt: Optional[str] = None,
            user_prompt: Optional[str] = None
    ) -> Tuple[Dict[str, Any], TokenUsage]:
        """
        Execute a search API request to OpenAI.

        Implementation of the abstract method from the parent class.
        This method now supports two ways of providing prompts:
        1. Legacy mode: Pass a single combined prompt in the 'prompt' parameter
        2. Structured mode: Pass separate system_prompt and user_prompt parameters
        
        If both methods are used, structured mode takes precedence.
        """
        try:
            # Create the search tool
            search_tool = self._create_search_tool(search_context_size, user_location)

            # Determine if we're using structured prompts
            using_structured_prompts = system_prompt is not None or user_prompt is not None
            
            # For structured outputs, prepare schema information
            schema_description = ""
            if response_schema and hasattr(response_schema, "model_fields"):
                # Since the prompt already contains schema info, we'll only add minimal guidance
                schema_description = "Make sure your response follows the exact schema structure specified in the prompt."

            enhanced_prompt = ""
            
            if using_structured_prompts:
                # Use structured prompts with priority
                if system_prompt is None:
                    # Default system prompt for search if none provided
                    system_prompt = "You are a helpful assistant that provides accurate information based on web search results. Format your response as valid JSON."
                
                # Add schema guidance if needed
                if response_schema and hasattr(response_schema, "model_fields"):
                    system_prompt = f"{system_prompt}\n\n{schema_description}"
                
                # Use user prompt if provided, otherwise fall back to legacy prompt
                enhanced_prompt = user_prompt if user_prompt is not None else prompt
            else:
                # Legacy mode - combine system message with prompt
                if response_schema:
                    # The prompt already contains the schema and format instructions
                    enhanced_prompt = prompt
                else:
                    # For non-structured requests, add JSON formatting instruction
                    system_message = "You are a helpful assistant that provides accurate information based on web search results. Format your response as valid JSON."
                    enhanced_prompt = f"{system_message}\n\n{prompt}"

            # Use the responses API - web search doesn't support parse method
            # Prepare request parameters based on prompt mode
            request_params = {
                "model": self.model,
                "tools": [search_tool],
                "temperature": temperature if temperature is not None else self.default_temperature
            }
            
            # Add input parameters based on whether we're using structured prompts
            if using_structured_prompts:
                if system_prompt:
                    request_params["system"] = system_prompt
                request_params["input"] = enhanced_prompt
            else:
                request_params["input"] = enhanced_prompt
                
            response = await self.client.responses.create(**request_params)

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
                search_context_size=search_context_size,
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

    # ===============================
    # Search Utility Methods
    # ===============================

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
            logger.warning(f"Error extracting citations: {str(e)}")

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