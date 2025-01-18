import os
import logging
import json
from abc import ABC, abstractmethod
from typing import Dict, Any, Optional, Union
from openai import AsyncOpenAI
import google.generativeai as genai
from utils.token_usage import TokenUsage

logger = logging.getLogger(__name__)

class AIService(ABC):
    """Abstract base class for AI service providers."""

    def __init__(self):
        """Initialize service with token tracking."""
        self._token_usage = {}  # Dict to store token usage by operation tag
        self.provider_name = "base"  # Override in subclasses

    @abstractmethod
    async def generate_content(self, prompt: str, is_json: bool = True, operation_tag: str = "default") -> Union[Dict[str, Any], str]:
        """Generate content from prompt."""
        pass

    def get_token_usage(self, operation_tag: str) -> Optional[TokenUsage]:
        """Get token usage for specific operation."""
        return self._token_usage.get(operation_tag)

    def get_total_token_usage(self) -> Optional[TokenUsage]:
        """Get combined token usage across all operations."""
        if not self._token_usage:
            return None

        total = TokenUsage(
            operation_tag="total",
            prompt_tokens=0,
            completion_tokens=0,
            total_tokens=0,
            total_cost_in_usd=0.0,
            provider=self.provider_name
        )

        for usage in self._token_usage.values():
            total.add_tokens(usage)

        return total

    def _track_usage(self, usage: TokenUsage):
        """Track token usage by operation."""
        if usage.operation_tag in self._token_usage:
            self._token_usage[usage.operation_tag].add_tokens(usage)
        else:
            self._token_usage[usage.operation_tag] = usage

class OpenAIService(AIService):
    """OpenAI implementation of AI service."""

    def __init__(self):
        """Initialize OpenAI client."""
        super().__init__()
        self.provider_name = "openai"

        api_key = os.getenv("OPENAI_API_KEY")
        if not api_key:
            raise ValueError("OPENAI_API_KEY environment variable required")

        self.client = AsyncOpenAI(api_key=api_key)
        self.model = "gpt-4o-mini"  # Can be configured as needed

        # OpenAI pricing per 1K tokens (can be configured)
        self.price_per_1k_tokens = {
            "gpt-4o-mini": {
                "input": 0.01,
                "output": 0.03
            }
        }

    async def generate_content(self, prompt: str, is_json: bool = True, operation_tag: str = "default") -> Union[Dict[str, Any], str]:
        """Generate content using OpenAI."""
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

            if not response.choices:
                logger.warning("Empty response from OpenAI")
                self._track_usage(self._create_token_usage(0, 0, operation_tag))
                return {} if is_json else ""

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
            self._track_usage(token_usage)

            content = response.choices[0].message.content
            return json.loads(content) if is_json else content

        except Exception as e:
            logger.error(f"Error generating content with OpenAI: {str(e)}")
            self._track_usage(self._create_token_usage(0, 0, operation_tag))
            return {} if is_json else ""

    def _create_token_usage(self, prompt_tokens: int, completion_tokens: int, operation_tag: str) -> TokenUsage:
        """Create token usage object."""
        total_tokens = prompt_tokens + completion_tokens
        total_cost = (
                (prompt_tokens / 1000) * self.price_per_1k_tokens[self.model]["input"] +
                (completion_tokens / 1000) * self.price_per_1k_tokens[self.model]["output"]
        )

        return TokenUsage(
            operation_tag=operation_tag,
            prompt_tokens=prompt_tokens,
            completion_tokens=completion_tokens,
            total_tokens=total_tokens,
            total_cost_in_usd=total_cost,
            provider=self.provider_name
        )

class GeminiService(AIService):
    """Gemini implementation of AI service."""

    def __init__(self):
        """Initialize Gemini client."""
        super().__init__()
        self.provider_name = "gemini"

        api_key = os.getenv("GEMINI_API_TOKEN")
        if not api_key:
            raise ValueError("GEMINI_API_TOKEN environment variable required")

        genai.configure(api_key=api_key)
        self.model = genai.GenerativeModel('gemini-2.0-flash-exp')

        # Approximate token count for cost estimation
        self.avg_chars_per_token = 4
        self.cost_per_1k_tokens = 0.00015  # Example rate

    async def generate_content(self, prompt: str, is_json: bool = True, operation_tag: str = "default") -> Union[Dict[str, Any], str]:
        """Generate content using Gemini."""
        try:
            if is_json:
                prompt = f"{prompt}\n\nRespond in JSON format only."

            response = self.model.generate_content(prompt)
            if not response or not response.parts:
                logger.warning("Empty response from Gemini")
                self._track_usage(self._create_token_usage(prompt, "", operation_tag))
                return {} if is_json else ""

            # Track token usage
            response_text = response.parts[0].text
            token_usage = self._create_token_usage(prompt, response_text, operation_tag)
            self._track_usage(token_usage)

            if is_json:
                return self._parse_json_response(response_text)
            return response_text

        except Exception as e:
            logger.error(f"Error generating content with Gemini: {str(e)}")
            self._track_usage(self._create_token_usage(prompt, "", operation_tag))
            return {} if is_json else ""

    def _parse_json_response(self, response: str) -> Dict[str, Any]:
        """Parse JSON from Gemini response."""
        try:
            # Clean response text
            text = response.strip()
            if text.startswith("```json"):
                text = text[7:]
            if text.endswith("```"):
                text = text[:-3]
            text = text.strip()

            return json.loads(text)

        except Exception as e:
            logger.error(f"Error parsing JSON response: {str(e)}")
            return {}

    def _create_token_usage(self, prompt: str, response: str, operation_tag: str) -> TokenUsage:
        """Estimate token usage for Gemini."""
        # Rough estimation of tokens based on character count
        prompt_tokens = len(prompt) // self.avg_chars_per_token
        completion_tokens = len(response) // self.avg_chars_per_token
        total_tokens = prompt_tokens + completion_tokens

        # Approximate cost calculation
        total_cost = total_tokens * self.cost_per_1k_tokens

        return TokenUsage(
            operation_tag=operation_tag,
            prompt_tokens=prompt_tokens,
            completion_tokens=completion_tokens,
            total_tokens=total_tokens,
            total_cost_in_usd=total_cost,
            provider=self.provider_name
        )

class AIServiceFactory:
    """Factory for creating AI service instances."""

    @staticmethod
    def create_service(provider: str = "openai") -> AIService:
        """Create an AI service instance."""
        if provider.lower() == "openai":
            return OpenAIService()
        elif provider.lower() == "gemini":
            return GeminiService()
        else:
            raise ValueError(f"Unsupported AI provider: {provider}")