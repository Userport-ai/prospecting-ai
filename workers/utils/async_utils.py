import asyncio
import concurrent.futures
import functools
import os
from typing import Any, Callable, Coroutine, TypeVar, Literal, Dict

from utils.loguru_setup import (
    logger,
    trace_id_var,
    account_id_var,
    task_name_var
)

T = TypeVar('T')

# Thumb rules for optimal thread counts based on system
# For I/O pool: Higher count is better as these operations are mostly waiting
# For CPU pool: Should match or be close to number of CPU cores
CPU_COUNT = os.cpu_count() or 4

# Create a dedicated thread pool for I/O operations (network, disk, etc.)
IO_THREAD_POOL = concurrent.futures.ThreadPoolExecutor(
    max_workers=min(32, CPU_COUNT * 10),  # Higher multiplier for I/O tasks
    thread_name_prefix="io-worker-"
)

# Create a dedicated thread pool for CPU-bound operations
CPU_THREAD_POOL = concurrent.futures.ThreadPoolExecutor(
    max_workers=CPU_COUNT,  # Match CPU count for CPU-intensive work
    thread_name_prefix="cpu-worker-"
)

def capture_context():
    """Capture current trace context variables."""
    context = {}

    # Capture trace_id if it exists
    trace_id = trace_id_var.get()
    if trace_id is not None:
        context['trace_id'] = trace_id

    # Capture account_id if it exists
    account_id = account_id_var.get()
    if account_id is not None:
        context['account_id'] = account_id

    # Capture task_name if it exists
    task_name = task_name_var.get()
    if task_name is not None:
        context['task_name'] = task_name

    return context

def apply_context(context: Dict[str, Any]):
    """Apply captured context to the current thread."""
    if 'trace_id' in context:
        trace_id_var.set(context['trace_id'])

    if 'account_id' in context:
        account_id_var.set(context['account_id'])

    if 'task_name' in context:
        task_name_var.set(context['task_name'])

def to_thread(
        func: Callable[..., T],
        pool_type: Literal["io", "cpu"] = "io"
) -> Callable[..., Coroutine[Any, Any, T]]:
    """
    Decorator to run a synchronous function in a dedicated thread pool.
    Preserves trace context across thread boundaries.

    Args:
        func: The synchronous function to run in a thread
        pool_type: Which thread pool to use - "io" for I/O-bound operations
                  or "cpu" for CPU-bound operations

    Returns:
        An async function that runs the original function in a thread
    """
    @functools.wraps(func)
    async def wrapper(*args: Any, **kwargs: Any) -> T:
        # Capture current context before switching to thread
        context = capture_context()

        # Create a wrapped function that applies context in the new thread
        @functools.wraps(func)
        def context_wrapper(*fn_args, **fn_kwargs):
            # Apply the captured context in the new thread
            apply_context(context)
            try:
                # Run the actual function
                return func(*fn_args, **fn_kwargs)
            except Exception as e:
                # Log with the applied context
                logger.error(f"Error in thread function {func.__name__}: {e}", exc_info=True)
                raise

        # Run the context wrapper in the thread pool
        loop = asyncio.get_running_loop()
        executor = IO_THREAD_POOL if pool_type == "io" else CPU_THREAD_POOL
        return await loop.run_in_executor(
            executor,
            lambda: context_wrapper(*args, **kwargs)
        )

    return wrapper

# Convenience functions for specific pool types
def to_io_thread(func: Callable[..., T]) -> Callable[..., Coroutine[Any, Any, T]]:
    """Run a function in the I/O thread pool, preserving trace context"""
    return to_thread(func, pool_type="io")

def to_cpu_thread(func: Callable[..., T]) -> Callable[..., Coroutine[Any, Any, T]]:
    """Run a function in the CPU thread pool, preserving trace context"""
    return to_thread(func, pool_type="cpu")

# For direct execution without decorator
async def run_in_thread(
        func: Callable[..., T],
        *args: Any,
        pool_type: Literal["io", "cpu"] = "io",
        **kwargs: Any
) -> T:
    """
    Run a function in the specified thread pool, preserving trace context.

    Args:
        func: Function to run
        *args: Arguments to pass to the function
        pool_type: Which thread pool to use
        **kwargs: Keyword arguments to pass to the function

    Returns:
        Result of the function
    """
    # Capture current context
    context = capture_context()

    @functools.wraps(func)
    def context_wrapper(*fn_args, **fn_kwargs):
        # Apply the captured context in the new thread
        apply_context(context)
        try:
            # Run the actual function
            return func(*fn_args, **fn_kwargs)
        except Exception as e:
            # Log with the applied context
            logger.error(f"Error in thread function {func.__name__}: {e}", exc_info=True)
            raise

    # Run the context wrapper in the thread pool
    loop = asyncio.get_running_loop()
    executor = IO_THREAD_POOL if pool_type == "io" else CPU_THREAD_POOL
    return await loop.run_in_executor(
        executor,
        lambda: context_wrapper(*args, **kwargs)
    )

# To properly clean up the thread pools when the application shuts down
async def shutdown_thread_pools():
    """Shutdown all thread pools gracefully."""
    logger.info("Shutting down thread pools")
    # First shutdown CPU pool as it might depend on I/O operations
    CPU_THREAD_POOL.shutdown(wait=True)
    IO_THREAD_POOL.shutdown(wait=True)
    logger.info("Thread pools shutdown complete")