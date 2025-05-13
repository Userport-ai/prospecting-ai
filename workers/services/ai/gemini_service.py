import os
import enum
from typing import Dict, Any, Optional, Union, Tuple

import random
import google.genai as genai
from google.api_core.exceptions import ResourceExhausted as GoogleAPIResourceExhausted
from google.genai import types

from utils.async_utils import to_thread, to_cpu_thread
from utils.retry_utils import RetryableError, RetryConfig, with_retry
from utils.token_usage import TokenUsage
from utils.loguru_setup import logger
from services.ai.ai_cache_service import AICacheService
from services.ai.ai_service_base import AIService, ThinkingBudget

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
            default_temperature: Optional[float] = 0.0,  # Default to 0.0 for deterministic outputs
            thinking_budget: Optional[ThinkingBudget] = None
    ):
        """Initialize Gemini client."""
        super().__init__(
            model_name=model_name,
            cache_service=cache_service,
            tenant_id=tenant_id,
            default_temperature=default_temperature
        )
        self.thinking_budget = thinking_budget
        self.provider_name = "gemini"

        api_key = os.getenv("GEMINI_API_TOKEN")
        if not api_key:
            raise ValueError("GEMINI_API_TOKEN environment variable required")

        # Create client instead of configuring globally
        self.client = genai.Client(api_key=api_key)
        self.model = model_name or 'gemini-2.5-flash-preview-04-17'
        self.fallback_model = 'gemini-2.5-flash-preview-04-17'

        # Approximate token count for cost estimation
        self.avg_chars_per_token = 4
        self.cost_per_1k_tokens = 0.00015  # Example rate

    @staticmethod
    def _should_fallback(error: Exception) -> bool:
        """Check if error indicates need for fallback model."""
        error_str = str(error).lower()
        return (
                '500' in error_str or '503' in error_str or
                'internal server error' in error_str or
                'service unavailable' in error_str or
                isinstance(error, GoogleAPIResourceExhausted)
        )

    # ===============================
    # Core Content Generation Methods
    # ===============================

    @with_retry(retry_config=GEMINI_RETRY_CONFIG, operation_name="_gemini_generate_content")
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
        """Generate content using Gemini without using cache.

        This method now supports two ways of providing prompts:
        1. Legacy mode: Pass a single combined prompt in the 'prompt' parameter
        2. Structured mode: Pass separate system_prompt and user_prompt parameters

        If both methods are used, structured mode takes precedence.
        """
        try:
            # Create config for the API call
            config_params = {}

            # Use provided temperature or default
            used_temperature = temperature if temperature is not None else self.default_temperature
            if used_temperature is not None:
                config_params['temperature'] = used_temperature

            # Determine which prompt to use based on parameters
            final_prompt = ""

            if system_prompt is not None or user_prompt is not None:
                # Structured mode - build combined prompt with system and user parts
                # For Gemini we need to combine them as it doesn't have native system/user roles
                system_part = system_prompt or ""
                user_part = user_prompt or ""

                if system_part and user_part:
                    final_prompt = f"SYSTEM INSTRUCTIONS:\n{system_part}\n\nUSER MESSAGE:\n{user_part}"
                elif system_part:
                    final_prompt = system_part
                elif user_part:
                    final_prompt = user_part
            else:
                # Legacy mode - use the prompt parameter
                final_prompt = prompt or ""

            # Add JSON format instruction if needed
            if is_json:
                config_params['response_mime_type'] = 'application/json'

            response = None
            max_attempts = 3
            # Try multiple times before falling back
            for i in range(max_attempts):
                try:
                    response = await self._generate_content_in_thread(final_prompt, config_params, thinking_budget)
                    if response and hasattr(response, 'text') and response.text is not None:
                        # Success with primary model
                        break
                    logger.warning(f"Empty response from primary model, retrying... (attempt {i+1})")
                except Exception as e:
                    logger.warning(f"Error in generate_content_in_thread (attempt {i+1}): {e}")
                    response = None

                    # If it's a fallback-worthy error on the last attempt, try fallback
                    if i == (max_attempts - 1) and (self._should_fallback(e) or not response):
                        logger.warning(f"Primary model failed after 3 attempts, trying fallback: {e}")
                        try:
                            response = await self._generate_content_in_thread(
                                final_prompt,
                                config_params,
                                thinking_budget,
                                _override_model=self.fallback_model
                            )
                            if response and hasattr(response, 'text') and response.text is not None:
                                logger.info(f"Fallback to {self.fallback_model} successful")
                            else:
                                raise ValueError("Empty response from fallback model")
                        except Exception as fallback_error:
                            logger.error(f"Fallback model also failed: {fallback_error}")
                            raise e

            if not response or not hasattr(response, 'text') or response.text is None:
                logger.warning("Final attempt: Empty or invalid response from Gemini")
                token_usage = self._create_token_usage(0, 0, operation_tag)
                return {} if is_json else "", token_usage

            response_text = response.text
            logger.debug(f"Gemini response: {response}")

            # Estimate token usage based on character count
            try:
                prompt_tokens = 0
                if final_prompt:
                    prompt_tokens = len(final_prompt) // self.avg_chars_per_token

                completion_tokens = 0
                if response_text:
                    completion_tokens = len(response_text) // self.avg_chars_per_token

                total_tokens = prompt_tokens + completion_tokens
                total_cost = (total_tokens / 1000) * self.cost_per_1k_tokens

                token_usage = self._create_token_usage(
                    prompt_tokens=prompt_tokens,
                    completion_tokens=completion_tokens,
                    operation_tag=operation_tag,
                    total_cost=total_cost
                )
            except Exception as e:
                logger.warning(f"Error calculating token usage: {str(e)}")
                token_usage = self._create_token_usage(0, 0, operation_tag)

            if is_json:
                try:
                    result = await self._parse_json_response_async(response_text)
                    return result, token_usage
                except Exception as e:
                    logger.error(f"Error parsing JSON response: {str(e)}")
                    return {}, token_usage

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
            operation_tag: str = "search",
            temperature: Optional[float] = None,
            thinking_budget: Optional[ThinkingBudget] = None,
            system_prompt: Optional[str] = None,
            user_prompt: Optional[str] = None
    ) -> Tuple[Dict[str, Any], TokenUsage]:
        """Execute search request using Gemini API."""
        try:
            # Configure search parameters
            search_params = {}

            if response_schema and hasattr(response_schema, "model_fields"):
                schema_description = []
                for field_name, field_info in response_schema.model_fields.items():
                    field_type = str(field_info.annotation)
                    description = getattr(field_info, "description", "")
                    schema_description.append(f"- {field_name}: {field_type}{' - ' + description if description else ''}")

            if user_location:
                search_params["user_location"] = user_location

            # Try multiple times until grounding result is found.
            current_temperature = temperature if temperature is not None else self.default_temperature
            response = None
            used_fallback = False

            for i in range(3):
                # Run in thread since we're using the synchronous API
                try:
                    response = await self._generate_search_content_in_thread(
                        prompt=prompt,
                        search_params=search_params,
                        temperature=current_temperature,
                        thinking_budget=thinking_budget
                    )
                except Exception as search_error:
                    # Try fallback if it's a fallback-worthy error
                    if self._should_fallback(search_error):
                        logger.warning(f"Primary search model failed, trying fallback: {search_error}")
                        try:
                            response = await self._generate_search_content_in_thread(
                                prompt=prompt,
                                search_params=search_params,
                                temperature=current_temperature,
                                thinking_budget=thinking_budget,
                                _override_model=self.fallback_model
                            )
                            used_fallback = True
                            logger.info(f"Search fallback to {self.fallback_model} successful")
                        except Exception as fallback_error:
                            logger.error(f"Search fallback also failed: {fallback_error}")
                            response = None
                    else:
                        response = None

                logger.debug(f"Gemini search response : {response}...")

                # Check if response is valid before accessing its properties
                if not response or not hasattr(response, 'candidates') or not response.candidates:
                    logger.warning("Empty or invalid search response from Gemini")
                    # Adjust temperature and try again
                    current_temperature = random.uniform(0, 0.3)
                    continue

                if not hasattr(response.candidates[0], 'grounding_metadata'):
                    logger.warning("Response lacks grounding_metadata")
                    current_temperature = random.uniform(0, 0.3)
                    continue

                if not hasattr(response.candidates[0].grounding_metadata, 'web_search_queries'):
                    logger.warning("Response lacks web_search_queries attribute")
                    current_temperature = random.uniform(0, 0.3)
                    continue

                # Check if grounding happened
                if (
                        response.candidates[0].grounding_metadata.web_search_queries is not None
                        or (
                        hasattr(response.candidates[0].grounding_metadata, 'search_entry_point')
                        and hasattr(response.candidates[0].grounding_metadata.search_entry_point, 'rendered_content')
                        and response.candidates[0].grounding_metadata.search_entry_point.rendered_content is not None
                )
                ):
                    # Response grounded in web search.
                    logger.debug(f"Gemini search grounded at temperature: {current_temperature} in attempt number: {i+1}")
                    logger.debug(f"Gemini web search queries performed: {response.candidates[0].grounding_metadata.web_search_queries}")
                    break
                else:
                    # Response is not grounded in web search, try with another temperature.
                    logger.debug(f"Gemini search was not grounded at temperature: {current_temperature} in attempt number: {i+1}")
                    current_temperature = random.uniform(0, 0.3)

            if not response or not hasattr(response, 'text'):
                logger.warning("Empty search response from Gemini")
                raise ValueError("Empty response from Gemini")

            response_text = response.text

            # Process grounding metadata to extract sources and their relationships to response segments
            try:
                sources, segment_source_mapping, source_segments = self._process_grounding_metadata(
                    response.candidates[0].grounding_metadata,
                    response_text
                )
            except Exception as e:
                logger.warning(f"Error processing grounding metadata: {str(e)}")
                sources, segment_source_mapping, source_segments = [], {}, {}

            # Estimate token usage with search multiplier
            multiplier = 1.0

            prompt_tokens = len(prompt) // self.avg_chars_per_token
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

            # Create a combined markdown representation of all sources
            all_sources_markdown = self._create_all_sources_markdown(sources)

            # Parse JSON response if needed
            if response_schema:
                result = await self._parse_json_response_async(response_text)
                # Add metadata about the search - use correct model name
                actual_model = self.fallback_model if used_fallback else self.model
                result["_search_metadata"] = {
                    "provider": self.provider_name,
                    "model": actual_model,
                    "search_context_size": search_context_size,
                    "sources": sources,
                    "sources_markdown": all_sources_markdown,
                    "segment_source_mapping": segment_source_mapping,
                    "source_segments": source_segments,
                    "web_search_queries": response.candidates[0].grounding_metadata.web_search_queries or []
                }
                return result, token_usage

            # For non-JSON responses, add sources as structured data
            if sources:
                return (response_text + "\n\n" + all_sources_markdown), token_usage

            return response_text, token_usage

        except Exception as e:
            logger.error(f"Error in Gemini search request: {str(e)}", exc_info=True)
            # Return empty dict to respect contract
            prompt_len = len(prompt) if prompt else 0
            token_usage = self._create_token_usage(prompt_len // 4, 10, operation_tag, 0.001)
            return {}, token_usage

    def _process_grounding_metadata(self, grounding_metadata, response_text):
        """Process grounding metadata to extract sources and their relationship to the response text."""
        sources = []
        segment_source_mapping = {}  # Maps segments of text to source indices
        source_segments = {}  # Maps source indices to segments they support

        # Process grounding chunks (the actual sources)
        grounding_chunks = getattr(grounding_metadata, 'grounding_chunks', [])
        if grounding_chunks:
            for idx, chunk in enumerate(grounding_chunks):
                # Extract web information if available
                if hasattr(chunk, 'web') and chunk.web:
                    source = {
                        'id': idx,
                        'type': 'web',
                        'title': getattr(chunk.web, 'title', f"Source {idx}"),
                        'domain': getattr(chunk.web, 'domain', None),
                        'uri': getattr(chunk.web, 'uri', None),
                    }

                    # Create markdown representation for this source
                    markdown = self._create_source_markdown(
                        idx,
                        source['title'],
                        source['uri'],
                        None,  # No snippet available directly in chunk
                        None   # No publish date available
                    )
                    source['markdown'] = markdown

                    sources.append(source)
                    source_segments[idx] = []  # Initialize empty list for segments

        # Process grounding supports (connections between text segments and sources)
        grounding_supports = getattr(grounding_metadata, 'grounding_supports', [])
        if grounding_supports:
            for support_idx, support in enumerate(grounding_supports):
                if (hasattr(support, 'segment') and support.segment and
                        hasattr(support, 'grounding_chunk_indices')):

                    segment_text = getattr(support.segment, 'text', '')
                    start_index = getattr(support.segment, 'start_index', None)
                    end_index = getattr(support.segment, 'end_index', None)

                    # Create segment identifier
                    segment_id = f"segment_{support_idx}"

                    # Map segment to sources
                    chunk_indices = support.grounding_chunk_indices
                    segment_source_mapping[segment_id] = {
                        'text': segment_text,
                        'start_index': start_index,
                        'end_index': end_index,
                        'source_indices': chunk_indices
                    }

                    # Add segment to each source's supported segments
                    for chunk_idx in chunk_indices:
                        if chunk_idx in source_segments:
                            source_segments[chunk_idx].append({
                                'segment_id': segment_id,
                                'text': segment_text,
                                'start_index': start_index,
                                'end_index': end_index
                            })

        # Add search entry point links if available
        if (hasattr(grounding_metadata, 'search_entry_point') and
                grounding_metadata.search_entry_point):

            search_entry_point = grounding_metadata.search_entry_point

            # Extract rendered results if available
            if hasattr(search_entry_point, 'rendered_results'):
                rendered_results = search_entry_point.rendered_results
                for idx, result in enumerate(rendered_results):
                    source_idx = len(sources)
                    source = {
                        'id': source_idx,
                        'type': 'search_entry_point',
                        'title': getattr(result, 'title', f"Related Search {idx}"),
                        'url': getattr(result, 'url', None),
                        'snippet': getattr(result, 'snippet', None)
                    }

                    # Create markdown representation
                    markdown = self._create_source_markdown(
                        idx,
                        source['title'],
                        source['url'],
                        source['snippet'],
                        None  # No publish date
                    )
                    source['markdown'] = markdown

                    sources.append(source)

        return sources, segment_source_mapping, source_segments

    @staticmethod
    def _create_source_markdown(idx, title, url, snippet, published_date):
        """Create a markdown representation of a single source."""
        markdown = []

        # Format as numbered list item with link if URL is available
        if url:
            markdown.append(f"{idx+1}. [{title}]({url})")
        else:
            markdown.append(f"{idx+1}. **{title}**")

        # Add snippet if available
        if snippet:
            # Clean the snippet - remove newlines and excessive spaces
            cleaned_snippet = ' '.join(snippet.split())
            markdown.append(f"   > {cleaned_snippet}")

        # Add published date if available
        if published_date:
            markdown.append(f"   *Published: {published_date}*")

        # Join with newlines
        return '\n'.join(markdown)

    @staticmethod
    def _create_all_sources_markdown(sources):
        """Create a combined markdown representation of all sources."""
        if not sources:
            return ""

        markdown = ["## Sources\n"]

        for source in sources:
            # Each source already has its own markdown representation
            markdown.append(source.get('markdown', ''))
            markdown.append("")  # Empty line between sources

        return '\n'.join(markdown)

    # ===============================
    # Thread Execution Helpers
    # ===============================

    @to_thread
    def _generate_content_in_thread(self, prompt: str, config_params: Dict[str, Any], thinking_budget: Optional[ThinkingBudget] = None, _override_model: Optional[str] = None):
        """Run Gemini's synchronous generate_content in a separate thread"""
        # Create a GenerateContentConfig object from the config dictionary
        config = types.GenerateContentConfig(**config_params) if config_params else None

        # Use provided thinking_budget if available, otherwise use the default
        current_thinking_budget = thinking_budget if thinking_budget is not None else self.thinking_budget

        # Use override model if provided, otherwise use instance model
        model_to_use = _override_model or self.model

        # Apply thinking budget if model is gemini-2.5-flash and thinking_budget is set
        if model_to_use and model_to_use.startswith('gemini-2.5') and current_thinking_budget:
            if not config:
                config = types.GenerateContentConfig()
            config.thinking_config = types.ThinkingConfig(
                thinking_budget=current_thinking_budget.value if isinstance(current_thinking_budget, enum.Enum) else 0,
                include_thoughts=True
            )

        # Set response mime type if provided
        if 'response_mime_type' in config_params:
            config.response_mime_type = config_params['response_mime_type']

        return self.client.models.generate_content(
            model=model_to_use,
            contents=prompt,
            config=config
        )

    @to_thread
    def _generate_search_content_in_thread(self, prompt: str, search_params: Dict[str, Any], temperature: Optional[float] = None, thinking_budget: Optional[ThinkingBudget] = None, _override_model: Optional[str] = None):
        """Execute Gemini's search-enabled content generation in a separate thread."""
        # Create the Google Search tool
        search_tool = types.Tool(google_search=types.GoogleSearch())

        # Prepare generation config
        config_params = {}
        if temperature is not None:
            config_params['temperature'] = temperature

        # Create config
        config = types.GenerateContentConfig(
            tools=[search_tool],
            **config_params
        )

        # Use provided thinking_budget if available, otherwise use the default
        current_thinking_budget = thinking_budget if thinking_budget is not None else self.thinking_budget

        # Use override model if provided, otherwise use instance model
        model_to_use = _override_model or self.model

        # Apply thinking budget if model is gemini-2.5-flash and thinking_budget is set
        if model_to_use and model_to_use.startswith('gemini-2.5') and current_thinking_budget:
            config.thinking_config = types.ThinkingConfig(
                thinking_budget=current_thinking_budget.value if isinstance(current_thinking_budget, enum.Enum) else 0,
                include_thoughts=True
            )

        return self.client.models.generate_content(
            model=model_to_use,
            contents=prompt,
            config=config
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