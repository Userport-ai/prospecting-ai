import os
import sys
import json
import logging
import traceback
from typing import Dict, Any, Optional, List

from loguru import logger


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

        # Process extra fields
        has_exc_info = False
        for k, v in record["extra"].items():
            if k == "exc_info" and v is True:
                has_exc_info = True
            else:
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
            logger.opt(exception=True).critical(
                "Uncaught exception: {}", str(exc_value)
            )
        # Call the original exception handler
        return original_excepthook(exc_type, exc_value, exc_traceback)

    sys.excepthook = exception_logger

    return logger

# Initialize logger
logger = setup_logging()