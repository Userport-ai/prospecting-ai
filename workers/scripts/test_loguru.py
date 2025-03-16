#!/usr/bin/env python3
"""Enhanced test script for loguru integration with better exception testing."""

import os
import sys

# Add parent directory to Python path
sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from utils.loguru_setup import logger

# Test regular logging
logger.info("This is an info message", test_field="Test value")
logger.debug("This is a debug message")
logger.warning("This is a warning message")

# Test exception logging with simple exception
def shallow_error():
    # Intentionally cause an error
    return 1 / 0

try:
    shallow_error()
except Exception as e:
    # Method 1: Using exc_info=True parameter
    logger.error(f"Simple exception with exc_info=True: {e}", operation="shallow_exc_info", exc_info=True)

    # Method 2: Using opt(exception=True)
    logger.opt(exception=True).error(f"Simple exception with opt(exception=True): {e}", operation="shallow_opt")

# Test exception logging with nested exception
def first_level():
    return second_level()

def second_level():
    return third_level()

def third_level():
    # Intentionally cause an error
    return 1 / 0

try:
    first_level()
except Exception as e:
    # Method 1: Using exc_info=True parameter
    logger.error(f"Nested exception with exc_info=True: {e}", operation="nested_exc_info", exc_info=True)

    # Method 2: Using opt(exception=True)
    logger.opt(exception=True).error(f"Nested exception with opt(exception=True): {e}", operation="nested_opt")

# Test exception chaining (using 'raise from')
try:
    try:
        # Primary exception
        open("non_existent_file.txt")
    except FileNotFoundError as e:
        # Secondary exception that wraps the first
        raise ValueError("Configuration error") from e
except Exception as e:
    # Method 1: Using exc_info=True parameter
    logger.error(f"Chained exception with exc_info=True: {e}", operation="chained_exc_info", exc_info=True)

    # Method 2: Using opt(exception=True)
    logger.opt(exception=True).error(f"Chained exception with opt(exception=True): {e}", operation="chained_opt")

# Test exception in bound logger
task_logger = logger.bind(task_id="123", job_id="456")
try:
    # Intentionally cause an error
    x = {"key": "value"}
    missing = x["missing_key"]
except Exception as e:
    task_logger.opt(exception=True).error(f"Exception in bound logger: {e}")

# Test log levels
logger.debug("Debug level message")
logger.info("Info level message")
logger.warning("Warning level message")
logger.error("Error level message")
logger.critical("Critical level message")