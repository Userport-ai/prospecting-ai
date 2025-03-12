import asyncio
import contextvars
import json
import logging
import os
import sys
import traceback
import uuid
from typing import Dict, Any, Optional

from loguru import logger


def capture_context() -> Dict[str, Any]:
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

def restore_context(context: Dict[str, Any]) -> None:
    """Restore captured context variables."""
    if 'trace_id' in context:
        trace_id_var.set(context['trace_id'])

    if 'account_id' in context:
        account_id_var.set(context['account_id'])

    if 'task_name' in context:
        task_name_var.set(context['task_name'])

def setup_context_preserving_task_factory():
    """
    Configure asyncio to preserve context variables across all task boundaries.
    Call this once during application startup.

    Note: This only affects tasks created with asyncio.create_task() AFTER this function is called.
    It won't affect tasks created by third-party libraries or before this is called.
    For those cases, use create_task_with_context() instead.
    """
    loop = asyncio.get_running_loop()

    # Store the original task factory if it exists
    original_task_factory = loop.get_task_factory()

    def context_preserving_task_factory(loop, coro, **kwargs):
        """Task factory that preserves context across task boundaries"""
        # Capture current context
        context = capture_context()

        # Create a wrapper coroutine that restores context
        async def context_wrapper():
            # Restore the captured context
            restore_context(context)
            # Execute the original coroutine
            return await coro

        # Use the original factory if it exists, otherwise create a Task directly
        if original_task_factory is not None:
            return original_task_factory(loop, context_wrapper(), **kwargs)
        else:
            return asyncio.tasks.Task(context_wrapper(), loop=loop, **kwargs)

    # Set our custom task factory
    loop.set_task_factory(context_preserving_task_factory)

def create_task_with_context(coro, *, name=None):
    """
    Create a new task that preserves the current context variables.
    Use this for creating tasks when setup_context_preserving_task_factory
    hasn't been called or for third-party libraries.
    """
    # Capture current context
    context = capture_context()

    # Create a wrapper coroutine that restores context
    async def context_wrapper():
        # Restore the captured context
        restore_context(context)
        # Execute the original coroutine
        return await coro

    # Create and return the task
    return asyncio.create_task(context_wrapper(), name=name)

# Create context variables for trace_id, account_id, and task_name
trace_id_var = contextvars.ContextVar('trace_id', default=None)
account_id_var = contextvars.ContextVar('account_id', default=None)
task_name_var = contextvars.ContextVar('task_name', default=None)


def get_trace_id() -> str:
    """Get current trace ID or generate a new one if none exists."""
    trace_id = trace_id_var.get()
    if not trace_id:
        trace_id = str(uuid.uuid4())
        trace_id_var.set(trace_id)
    return trace_id


def set_trace_context(trace_id: Optional[str] = None,
                      account_id: Optional[str] = None,
                      task_name: Optional[str] = None) -> Dict[str, Any]:
    """
    Set trace context variables and return a token dictionary that can be used to reset context.

    Args:
        trace_id: Trace ID to set (generates new UUID if None)
        account_id: Account ID to set
        task_name: Task name to set

    Returns:
        Dictionary of reset tokens
    """
    tokens = {}

    # Set trace_id (generate if not provided)
    trace_id_to_set = trace_id if trace_id else str(uuid.uuid4())
    tokens['trace_id'] = trace_id_var.set(trace_id_to_set)

    # Set account_id if provided
    if account_id is not None:
        tokens['account_id'] = account_id_var.set(account_id)

    # Set task_name if provided
    if task_name is not None:
        tokens['task_name'] = task_name_var.set(task_name)

    return tokens


def reset_trace_context(tokens: Dict[str, Any]) -> None:
    """
    Reset context variables using tokens from set_trace_context.

    Args:
        tokens: Dictionary of reset tokens from set_trace_context
    """
    for var_name, token in tokens.items():
        if var_name == 'trace_id' and token:
            trace_id_var.reset(token)
        elif var_name == 'account_id' and token:
            account_id_var.reset(token)
        elif var_name == 'task_name' and token:
            task_name_var.reset(token)


class TraceContextAdapter:
    """Adapter class to add trace context to logger calls."""

    def __init__(self, logger_instance):
        self._logger = logger_instance

    def _add_context(self, kwargs):
        """Add trace context to log record if not already present."""
        # Add trace_id if not explicitly provided
        if 'trace_id' not in kwargs:
            trace_id = trace_id_var.get()
            if trace_id:
                kwargs['trace_id'] = trace_id

        # Add account_id if not explicitly provided and available in context
        if 'account_id' not in kwargs:
            account_id = account_id_var.get()
            if account_id:
                kwargs['account_id'] = account_id

        # Add task_name if not explicitly provided and available in context
        if 'task_name' not in kwargs:
            task_name = task_name_var.get()
            if task_name:
                kwargs['task_name'] = task_name

        return kwargs

    def debug(self, message, **kwargs):
        kwargs = self._add_context(kwargs)
        return self._logger.debug(message, **kwargs)

    def info(self, message, **kwargs):
        kwargs = self._add_context(kwargs)
        return self._logger.info(message, **kwargs)

    def warning(self, message, **kwargs):
        kwargs = self._add_context(kwargs)
        return self._logger.warning(message, **kwargs)

    def error(self, message, **kwargs):
        kwargs = self._add_context(kwargs)
        return self._logger.error(message, **kwargs)

    def critical(self, message, **kwargs):
        kwargs = self._add_context(kwargs)
        return self._logger.critical(message, **kwargs)

    def exception(self, message, **kwargs):
        kwargs = self._add_context(kwargs)
        return self._logger.exception(message, **kwargs)

    def log(self, level, message, **kwargs):
        kwargs = self._add_context(kwargs)
        return self._logger.log(level, message, **kwargs)

    def opt(self, *args, **kwargs):
        # Create a new adapter with the opt result
        opt_logger = self._logger.opt(*args, **kwargs)
        return TraceContextAdapter(opt_logger)

    def bind(self, **kwargs):
        # Create a new adapter with the bind result
        bind_logger = self._logger.bind(**kwargs)
        return TraceContextAdapter(bind_logger)

    # Add this method to fix the error
    def level(self, name):
        """Forward level calls to the underlying logger."""
        return self._logger.level(name)

    def __getattr__(self, name):
        """Forward any other attribute access to the underlying logger."""
        return getattr(self._logger, name)


def setup_logging():
    """Configure loguru with custom formatting and enhanced exception handling."""

    # Remove default handler
    logger.remove()

    # Get log level from environment
    log_level = os.getenv('LOG_LEVEL', 'DEBUG').upper()

    # Create a custom sink that formats logs as JSON with enhanced exception handling
    def sink(message):
        # Extract message record
        record = message.record

        # Build basic log structure
        log_data = {
            "timestamp": record["time"].strftime("%Y-%m-%dT%H:%M:%S.%fZ"),
            "severity": record["level"].name,
            "message": record["message"],
            "name": record["name"],
            "function": record["function"],
            "file": record["file"].name,
            "line": record["line"]
        }

        # Process extra fields - add trace context fields first if available
        for context_field in ['trace_id', 'account_id', 'task_name']:
            context_value = record["extra"].get(context_field)
            if context_value:
                log_data[context_field] = context_value

        # Process other extra fields
        has_exc_info = False
        for k, v in record["extra"].items():
            if k == "exc_info" and v is True:
                has_exc_info = True
            elif k not in ['trace_id', 'account_id', 'task_name']:  # Skip already processed context fields
                log_data[k] = v

        # Handle exception information
        if record["exception"] or has_exc_info:
            current_exc_info = sys.exc_info()

            # If we have a current exception, use it
            if current_exc_info and current_exc_info[0] is not None:
                exc_type, exc_value, exc_tb = current_exc_info
                tb_lines = traceback.format_exception(exc_type, exc_value, exc_tb)

                log_data["error"] = {
                    "type": exc_type.__name__,
                    "message": str(exc_value),
                    "traceback": tb_lines
                }
            # If no current exception, but record has exception info
            elif record["exception"]:
                # Convert record exception to string and format it nicely
                exception_str = str(record["exception"])
                log_data["error"] = {
                    "type": "Exception",
                    "message": exception_str,
                    "traceback": message.record["message"].split("\n")
                }

        # Output as JSON
        print(json.dumps(log_data))

    # Add custom sink handler with enhanced settings
    logger.add(
        sink,
        level=log_level,
        format="{message}",             # Let our sink handle formatting
        backtrace=True,                 # Show traceback for all errors
        diagnose=True,                  # Show variable values in traceback
        enqueue=False,                  # Disable enqueue for better exception context
        catch=True                      # Catch errors from the handler
    )

    # Add a separate sink just for capturing exceptions with full traceback
    def exception_sink(message):
        # This is needed to always get the traceback in the message
        # We don't output anything from this sink, it's just to ensure
        # Loguru captures the traceback in the message
        pass

    logger.add(
        exception_sink,
        level=log_level,
        format="{message}\n{exception}",
        backtrace=True,
        diagnose=True,
        enqueue=False,
        catch=True
    )

    # Intercept standard library logging
    class InterceptHandler(logging.Handler):
        def emit(self, record):
            # Get corresponding Loguru level if it exists
            try:
                level = logger.level(record.levelname).name
            except ValueError:
                level = record.levelno

            # Find caller from where originated the logged message
            frame, depth = logging.currentframe(), 2
            while frame and frame.f_code.co_filename == logging.__file__:
                frame = frame.f_back
                depth += 1

            # Gather extra data
            extras = {}
            for key, value in record.__dict__.items():
                if key not in {"args", "asctime", "created", "exc_info", "exc_text",
                               "filename", "funcName", "id", "levelname", "levelno",
                               "lineno", "module", "msecs", "message", "msg", "name",
                               "pathname", "process", "processName", "relativeCreated",
                               "stack_info", "thread", "threadName"}:
                    extras[key] = value

            # Add trace context if available
            trace_id = trace_id_var.get()
            if trace_id and 'trace_id' not in extras:
                extras['trace_id'] = trace_id

            account_id = account_id_var.get()
            if account_id and 'account_id' not in extras:
                extras['account_id'] = account_id

            task_name = task_name_var.get()
            if task_name and 'task_name' not in extras:
                extras['task_name'] = task_name

            # Pass exception info if present
            logger.opt(depth=depth, exception=record.exc_info is not None).bind(**extras).log(
                level, record.getMessage())

    # Set up interception for existing standard loggers
    logging.basicConfig(handlers=[InterceptHandler()], level=0, force=True)

    # Configure third-party loggers to avoid noise
    for logger_name in ["httpcore", "httpx", "urllib3"]:
        logging.getLogger(logger_name).setLevel(logging.WARNING)

    # Patch sys.excepthook to log uncaught exceptions
    original_excepthook = sys.excepthook

    def exception_logger(exc_type, exc_value, exc_traceback):
        """Log uncaught exceptions with full traceback before system handling."""
        if not issubclass(exc_type, KeyboardInterrupt):
            # Include trace context with uncaught exceptions
            extras = {}

            trace_id = trace_id_var.get()
            if trace_id:
                extras['trace_id'] = trace_id

            account_id = account_id_var.get()
            if account_id:
                extras['account_id'] = account_id

            task_name = task_name_var.get()
            if task_name:
                extras['task_name'] = task_name

            logger.opt(exception=True).bind(**extras).critical(
                "Uncaught exception: {}", str(exc_value)
            )
        # Call the original exception handler
        return original_excepthook(exc_type, exc_value, exc_traceback)

    sys.excepthook = exception_logger

    # Wrap logger with the adapter to automatically add trace context
    trace_logger = TraceContextAdapter(logger)

    return trace_logger

# Initialize logger with trace context
logger = setup_logging()