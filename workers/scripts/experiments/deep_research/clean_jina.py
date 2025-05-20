#!/usr/bin/env python
# -*- coding: utf-8 -*-

"""
Clean Jina implementation that uses environment variables and logging to control output.
Set environment variables before importing to suppress verbose logging.
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

# Import JinaSearch after setting up logging environment
try:
    from langchain_community.tools.jina_search import JinaSearch
    from langchain_community.utilities.jina_search import JinaSearchAPIWrapper
    from langchain.tools import BaseTool
    from pydantic import SecretStr, Field
    
    # Override the default JinaSearch tool to prevent duplicated intro text
    class JinaSearch(BaseTool):
        """Tool that searches the web using Jina AI's API."""

        name = "jina_search"
        description = """Searches the web using Jina's AI-powered search. 
        Use this for finding specific facts and information about companies, products, 
        recent events, or market data."""
        
        api_wrapper: JinaSearchAPIWrapper = Field(default_factory=JinaSearchAPIWrapper)
        
        def _run(self, query: str) -> str:
            """Run the query through Jina search and get back search results."""
            # This ensures we only get the actual search results, not the intro message
            return self.api_wrapper.run(query)
            
        async def _arun(self, query: str) -> str:
            """Run the query through Jina search and get back search results."""
            # This ensures we only get the actual search results, not the intro message
            return await self.api_wrapper.arun(query)
    
except ImportError:
    print("Jina search tools not available. Search functionality will be limited.")