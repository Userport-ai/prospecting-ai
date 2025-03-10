import asyncio
import functools
import concurrent.futures
import os
from typing import Any, Callable, Coroutine, TypeVar, Optional, Literal, Dict

from utils.tracing import capture_context, restore_context

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

def to_thread(
        func: Callable[..., T],
        pool_type: Literal["io", "cpu"] = "io"
) -> Callable[..., Coroutine[Any, Any, T]]:
    """
    Decorator to run a synchronous function in a dedicated thread pool.
    Propagates trace context from the calling coroutine to the thread.

    Args:
        func: The synchronous function to run in a thread
        pool_type: Which thread pool to use - "io" for I/O-bound operations
                  or "cpu" for CPU-bound operations

    Returns:
        An async function that runs the original function in a thread
    """
    @functools.wraps(func)
    async def wrapper(*args: Any, **kwargs: Any) -> T:
        # Capture the current trace context before switching to a thread
        context = capture_context()
        
        # Define a function that restores context in the thread before calling the original function
        def run_with_context():
            # Restore trace context in the thread
            restore_context(context)
            # Execute the original function
            return func(*args, **kwargs)
        
        loop = asyncio.get_running_loop()
        executor = IO_THREAD_POOL if pool_type == "io" else CPU_THREAD_POOL
        return await loop.run_in_executor(
            executor,
            run_with_context
        )
    return wrapper

# Convenience functions for specific pool types
def to_io_thread(func: Callable[..., T]) -> Callable[..., Coroutine[Any, Any, T]]:
    """Run a function in the I/O thread pool"""
    return to_thread(func, pool_type="io")

def to_cpu_thread(func: Callable[..., T]) -> Callable[..., Coroutine[Any, Any, T]]:
    """Run a function in the CPU thread pool"""
    return to_thread(func, pool_type="cpu")

# For direct execution without decorator
async def run_in_thread(
        func: Callable[..., T],
        *args: Any,
        pool_type: Literal["io", "cpu"] = "io",
        **kwargs: Any
) -> T:
    """
    Run a function in the specified thread pool.
    Propagates trace context from the calling coroutine to the thread.

    Args:
        func: Function to run
        *args: Arguments to pass to the function
        pool_type: Which thread pool to use
        **kwargs: Keyword arguments to pass to the function

    Returns:
        Result of the function
    """
    # Capture the current trace context before switching to a thread
    context = capture_context()
    
    # Define a function that restores context in the thread before calling the original function
    def run_with_context():
        # Restore trace context in the thread
        restore_context(context)
        # Execute the original function
        return func(*args, **kwargs)
    
    loop = asyncio.get_running_loop()
    executor = IO_THREAD_POOL if pool_type == "io" else CPU_THREAD_POOL
    return await loop.run_in_executor(
        executor,
        run_with_context
    )

# To properly clean up the thread pools when the application shuts down
async def shutdown_thread_pools():
    """Shutdown all thread pools gracefully."""
    # First shutdown CPU pool as it might depend on I/O operations
    CPU_THREAD_POOL.shutdown(wait=True)
    IO_THREAD_POOL.shutdown(wait=True)