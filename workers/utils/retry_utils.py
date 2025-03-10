import asyncio
import functools
import logging
import random
import time
from dataclasses import dataclass
from typing import List, Type, TypeVar, Callable, Any, Coroutine, Generic, Optional, Union, Dict

from utils.tracing import capture_context, restore_context

logger = logging.getLogger(__name__)

RETRYABLE_STATUS_CODES = {
    408,  # Request Timeout
    429,  # Too Many Requests
    500,  # Internal Server Error
    502,  # Bad Gateway
    503,  # Service Unavailable
    504,  # Gateway Timeout
}

T = TypeVar('T')

class RetryableError(Exception):
    """Exception that should trigger a retry."""
    pass


@dataclass
class RetryConfig:
    """Configuration for retry behavior."""
    max_attempts: int = 3
    base_delay: float = 1.0
    max_delay: float = 60.0
    retryable_exceptions: List[Type[Exception]] = None

    def __post_init__(self):
        if self.retryable_exceptions is None:
            self.retryable_exceptions = [RetryableError, asyncio.TimeoutError,
                                         ConnectionError,
                                         TimeoutError]


def with_retry(
        retry_config: RetryConfig,
        operation_name: str = "operation"
) -> Callable[[Callable[..., Coroutine[Any, Any, T]]], Callable[..., Coroutine[Any, Any, T]]]:
    """
    Decorator for retrying an async function with exponential backoff.
    Preserves trace context across retry attempts.

    Args:
        retry_config: Configuration for retry behavior
        operation_name: Name of the operation for logging purposes

    Returns:
        Decorated function that implements retry logic
    """
    def decorator(func: Callable[..., Coroutine[Any, Any, T]]) -> Callable[..., Coroutine[Any, Any, T]]:
        @functools.wraps(func)
        async def wrapper(*args: Any, **kwargs: Any) -> T:
            # Capture the current trace context at the start of the first attempt
            # This ensures we use the same trace context for all retry attempts
            original_context = capture_context()
            
            attempt = 0
            last_exception = None

            while attempt < retry_config.max_attempts:
                try:
                    # Restore the original trace context before each attempt
                    # This ensures retry attempts maintain the same trace info
                    restore_context(original_context)
                    
                    return await func(*args, **kwargs)
                except Exception as e:
                    # Check if this exception type should trigger a retry
                    should_retry = any(
                        isinstance(e, exception_type)
                        for exception_type in retry_config.retryable_exceptions
                    )

                    if not should_retry:
                        logger.exception(f"Non-retryable exception in {operation_name}")
                        raise

                    attempt += 1
                    last_exception = e

                    if attempt >= retry_config.max_attempts:
                        logger.warning(
                            f"Maximum retry attempts ({retry_config.max_attempts}) reached for {operation_name}"
                        )
                        break

                    # Calculate delay(seconds) with exponential backoff and jitter
                    delay = min(
                        retry_config.base_delay * (2 ** (attempt - 1)),
                        retry_config.max_delay
                    )
                    jitter = random.uniform(0, 0.1 * delay)
                    total_delay = delay + jitter

                    # Ensure trace context is present in retry logs
                    logger.warning(
                        f"Retry attempt {attempt} for {operation_name} after {total_delay:.2f}s delay. "
                        f"Error: {str(e)}"
                    )

                    # Wait before retrying
                    await asyncio.sleep(total_delay)

            # If we've exhausted our retries, raise the last exception
            if last_exception:
                # Make sure trace context is available in the final error log
                restore_context(original_context)
                logger.error(f"All retry attempts failed for {operation_name}")
                raise last_exception

            # This should never happen, but just in case
            raise RuntimeError(f"Unexpected error in retry logic for {operation_name}")

        return wrapper

    return decorator
