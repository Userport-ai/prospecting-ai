import os
import sys
import unittest
from unittest.mock import AsyncMock, patch

import pytest

# Add the root directory to the Python path
sys.path.insert(0, os.path.abspath(os.path.join(os.path.dirname(__file__), '../../')))

from utils.retry_utils import (
    RetryConfig,
    RetryableError,
    with_retry,
    AsyncRetry
)


# Helper functions for tests
async def fake_sleep(delay):
    """Mock implementation of asyncio.sleep that doesn't actually sleep."""
    # Just record the delay without actually sleeping
    fake_sleep.calls.append(delay)
    return None


# Reset the calls list before each test
@pytest.fixture(autouse=True)
def setup_fake_sleep():
    fake_sleep.calls = []
    yield


@pytest.mark.asyncio
async def test_with_retry_success():
    """Test successful execution with no retries needed."""
    mock_func = AsyncMock(return_value="success")

    retry_config = RetryConfig(max_attempts=3, base_delay=0.1)
    decorated_func = with_retry(retry_config, "test_operation")(mock_func)

    result = await decorated_func("arg1", kwarg1="value1")

    assert result == "success"
    mock_func.assert_called_once_with("arg1", kwarg1="value1")


@pytest.mark.asyncio
async def test_with_retry_eventually_succeeds():
    """Test function that fails initially but eventually succeeds."""
    mock_func = AsyncMock()
    # Fail twice, then succeed on the third attempt
    mock_func.side_effect = [
        RetryableError("First failure"),
        RetryableError("Second failure"),
        "success"
    ]

    retry_config = RetryConfig(max_attempts=3, base_delay=0.01)
    decorated_func = with_retry(retry_config, "test_operation")(mock_func)

    result = await decorated_func()

    assert result == "success"
    assert mock_func.call_count == 3


@pytest.mark.asyncio
async def test_with_retry_exhausts_attempts():
    """Test function that always fails and exhausts all retry attempts."""
    mock_func = AsyncMock(side_effect=RetryableError("Always fails"))

    retry_config = RetryConfig(max_attempts=3, base_delay=0.01)
    decorated_func = with_retry(retry_config, "test_operation")(mock_func)

    with pytest.raises(RetryableError, match="Always fails"):
        await decorated_func()

    assert mock_func.call_count == 3


@pytest.mark.asyncio
async def test_with_retry_non_retryable_exception():
    """Test that non-retryable exceptions are immediately raised."""
    error = ValueError("Non-retryable error")
    mock_func = AsyncMock(side_effect=error)

    retry_config = RetryConfig(max_attempts=3, base_delay=0.01)
    decorated_func = with_retry(retry_config, "test_operation")(mock_func)

    with pytest.raises(ValueError, match="Non-retryable error"):
        await decorated_func()

    # Should only be called once since the exception isn't retryable
    mock_func.assert_called_once()


@pytest.mark.asyncio
async def test_with_retry_custom_retryable_exceptions():
    """Test with custom retryable exceptions."""
    mock_func = AsyncMock()
    mock_func.side_effect = [
        ValueError("First failure"),  # Now retryable
        "success"
    ]

    retry_config = RetryConfig(
        max_attempts=3,
        base_delay=0.01,
        retryable_exceptions=[ValueError]
    )
    decorated_func = with_retry(retry_config, "test_operation")(mock_func)

    result = await decorated_func()

    assert result == "success"
    assert mock_func.call_count == 2


@pytest.mark.asyncio
async def test_with_retry_backoff_timing():
    """Test that backoff delay is properly calculated and applied."""
    mock_func = AsyncMock()
    mock_func.side_effect = [
        RetryableError("First failure"),
        RetryableError("Second failure"),
        "success"
    ]

    with patch("asyncio.sleep", fake_sleep):
        retry_config = RetryConfig(max_attempts=3, base_delay=0.1, max_delay=1.0)
        decorated_func = with_retry(retry_config, "test_operation")(mock_func)

        result = await decorated_func()

    assert result == "success"
    assert len(fake_sleep.calls) == 2  # Two retries needed

    # Check that delays follow exponential backoff (with some jitter)
    # First delay should be around base_delay (0.1)
    assert 0.08 <= fake_sleep.calls[0] <= 0.15
    # Second delay should be around base_delay * 2¹ (0.2)
    assert 0.15 <= fake_sleep.calls[1] <= 0.3

@pytest.mark.asyncio
async def test_max_delay():
    """Test that delay is capped at max_delay."""
    mock_func = AsyncMock()
    mock_func.side_effect = [
        RetryableError("First failure"),
        RetryableError("Second failure"),
        RetryableError("Third failure"),
        RetryableError("Fourth failure"),
        "success"
    ]

    with patch("asyncio.sleep", fake_sleep):
        # Set a low max_delay to see the cap in action
        retry_config = RetryConfig(max_attempts=5, base_delay=0.1, max_delay=0.4)
        decorated_func = with_retry(retry_config, "test_operation")(mock_func)

        result = await decorated_func()

    assert result == "success"
    assert len(fake_sleep.calls) == 4  # Four retries needed

    # First delay: ~0.1s
    # Second delay: ~0.2s
    # Third delay: ~0.4s (capped at max_delay)
    # Fourth delay: ~0.4s (still capped at max_delay)
    assert fake_sleep.calls[2] <= 0.44  # Allow for jitter
    assert fake_sleep.calls[3] <= 0.44  # Allow for jitter
