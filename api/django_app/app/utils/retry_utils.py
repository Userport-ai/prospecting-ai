import asyncio
import logging
from functools import wraps
from typing import Type, Callable, List, Optional, Any

logger = logging.getLogger(__name__)

RETRYABLE_STATUS_CODES = {
    408,  # Request Timeout
    429,  # Too Many Requests
    500,  # Internal Server Error
    502,  # Bad Gateway
    503,  # Service Unavailable
    504,  # Gateway Timeout
}

class RetryableError(Exception):
    """Base class for errors that can be retried."""
    pass

class RetryConfig:
    """Configuration for retry behavior."""
    def __init__(
            self,
            max_attempts: int = 3,
            base_delay: float = 1.0,
            max_delay: float = 10.0,
            exponential_base: float = 2,
            retryable_exceptions: Optional[List[Type[Exception]]] = None
    ):
        self.max_attempts = max_attempts
        self.base_delay = base_delay
        self.max_delay = max_delay
        self.exponential_base = exponential_base
        self.retryable_exceptions = retryable_exceptions or [
            RetryableError,
            asyncio.TimeoutError,
            ConnectionError,
            TimeoutError
        ]

def with_retry(
        retry_config: Optional[RetryConfig] = None,
        operation_name: Optional[str] = None
) -> Callable:
    """
    Decorator for retrying async operations with exponential backoff.

    Args:
        retry_config: Configuration for retry behavior
        operation_name: Name of operation for logging purposes
    """
    if retry_config is None:
        retry_config = RetryConfig()

    def decorator(func: Callable) -> Callable:
        @wraps(func)
        async def wrapper(*args, **kwargs) -> Any:
            last_exception = None
            operation = operation_name or func.__name__

            for attempt in range(retry_config.max_attempts):
                try:
                    return await func(*args, **kwargs)

                except Exception as e:
                    last_exception = e

                    # Check if exception is retryable
                    is_retryable = any(
                        isinstance(e, exc_type)
                        for exc_type in retry_config.retryable_exceptions
                    )

                    if not is_retryable:
                        logger.error(
                            f"Non-retryable error in {operation} on attempt {attempt + 1}/{retry_config.max_attempts}: {str(e)}"
                        )
                        raise

                    if attempt == retry_config.max_attempts - 1:
                        logger.error(
                            f"Operation {operation} failed after {retry_config.max_attempts} attempts. Last error: {str(e)}"
                        )
                        raise

                    # Calculate backoff delay
                    delay = min(
                        retry_config.base_delay * (retry_config.exponential_base ** attempt),
                        retry_config.max_delay
                    )

                    logger.warning(
                        f"Retryable error in {operation} on attempt {attempt + 1}/{retry_config.max_attempts}. "
                        f"Retrying in {delay:.2f}s. Error: {str(e)}"
                    )

                    await asyncio.sleep(delay)

            # This shouldn't be reached, but just in case
            raise last_exception

        return wrapper
    return decorator