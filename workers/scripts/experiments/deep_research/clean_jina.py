#!/usr/bin/env python
# -*- coding: utf-8 -*-

"""
Clean Jina implementation that uses environment variables and logging to control output.
Set environment variables before importing to suppress verbose logging.

This implementation includes:
1. Proper async handling for JinaSearch tool to prevent event loop blocking
2. Environment variable mapping between JINA_API_TOKEN and JINA_API_KEY
3. Suppressed Jina logging for cleaner output
"""

import os
import logging
import warnings
import sys
from typing import Optional, Dict, Any

# Set environment variables before importing
os.environ["JINA_LOG_LEVEL"] = "ERROR"
os.environ["GRPC_VERBOSITY"] = "ERROR"
os.environ["GLOG_minloglevel"] = "2"

# Handle Jina API key conflict - support both environment variable names
if "JINA_API_TOKEN" in os.environ and "JINA_API_KEY" not in os.environ:
    os.environ["JINA_API_KEY"] = os.environ["JINA_API_TOKEN"]
    print("Using JINA_API_TOKEN as JINA_API_KEY")
elif "JINA_API_KEY" in os.environ and "JINA_API_TOKEN" not in os.environ:
    os.environ["JINA_API_TOKEN"] = os.environ["JINA_API_KEY"]
    print("Using JINA_API_KEY as JINA_API_TOKEN")

# Configure logging
logging.getLogger("httpx").setLevel(logging.ERROR)
logging.getLogger("httpcore").setLevel(logging.ERROR)
logging.getLogger("langchain").setLevel(logging.WARNING)
logging.getLogger("jina").setLevel(logging.ERROR)
logging.getLogger("openai").setLevel(logging.WARNING)
logging.getLogger("urllib3").setLevel(logging.WARNING)
logging.getLogger("google.api_core").setLevel(logging.WARNING)
logging.getLogger("google.generativeai").setLevel(logging.WARNING)

# Suppress warnings
warnings.filterwarnings("ignore", category=DeprecationWarning)
warnings.filterwarnings("ignore", category=UserWarning, module="langchain")

# Configure root logger for cleaner output
logging.basicConfig(
    level=logging.INFO,
    format="%(message)s",
    handlers=[logging.StreamHandler(sys.stdout)]
)

# Note: This module no longer provides a custom JinaSearch implementation.
# It only sets up environment variables and logging configuration.
# Import JinaSearch directly from langchain_community.tools.jina_search in your code.
try:
    # Just check if imports are available, but don't export them from this module
    from langchain_community.tools.jina_search import JinaSearch
    from langchain_community.utilities.jina_search import JinaSearchAPIWrapper
    print("Jina search configuration complete. Import JinaSearch directly from langchain_community.tools.jina_search.")
except ImportError:
    print("Jina search tools not available. Search functionality will be limited.")