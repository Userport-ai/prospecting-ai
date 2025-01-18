from dataclasses import dataclass
from typing import Optional

@dataclass
class TokenUsage:
    """Provider-agnostic token usage tracking."""

    operation_tag: str
    prompt_tokens: int
    completion_tokens: int
    total_tokens: int
    total_cost_in_usd: float
    provider: str  # Added to track which AI provider was used

    def add_tokens(self, other: Optional['TokenUsage']) -> None:
        """Add tokens from another instance."""
        if not other:
            return

        if self.provider != other.provider:
            raise ValueError(f"Cannot combine token usage from different providers: {self.provider} vs {other.provider}")

        self.prompt_tokens += other.prompt_tokens
        self.completion_tokens += other.completion_tokens
        self.total_tokens += other.total_tokens
        self.total_cost_in_usd += other.total_cost_in_usd