import asyncio
import logging
import threading

logger = logging.getLogger(__name__)

def run_async_in_thread(async_func, *args, **kwargs):
    """
    Helper function to run an async function in a separate thread.

    Args:
        async_func: The async function to run
        *args, **kwargs: Arguments to pass to the async function
    """
    def thread_target():
        try:
            asyncio.run(async_func(*args, **kwargs))
        except Exception as e:
            logger.error(f"Error in async thread: {str(e)}", exc_info=True)

    thread = threading.Thread(target=thread_target)
    thread.daemon = False
    thread.start()
    return thread