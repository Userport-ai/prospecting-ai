import os
import asyncio
import httpx
from typing import Dict, Optional

from utils.connection_pool import ConnectionPool
from utils.retry_utils import RetryableError, RetryConfig, with_retry
from utils.loguru_setup import logger

JINA_RETRY_CONFIG = RetryConfig(
    max_attempts=3,
    base_delay=1.0,
    max_delay=20.0,
    retryable_exceptions=[
        RetryableError,
        asyncio.TimeoutError,
        ConnectionError,
        httpx.ConnectTimeout,
        httpx.ConnectError,
        httpx.ReadError,
    ]
)


class JinaService:
    """Service class for handling Jina operations for account enrichment data."""

    def __init__(self):
        # Use Jina Reader API to read a URL.
        self.JINA_READER_API = "https://r.jina.ai/"
        # User Jina Search API to do web search and return results.
        self.JINA_SEARCH_API = "https://s.jina.ai/"
        self.jina_api_token = os.getenv('JINA_API_TOKEN')
        self.API_TIMEOUT = 60.0  # timeout in seconds.
        self.pool = ConnectionPool(
            limits=httpx.Limits(
                max_keepalive_connections=10,
                max_connections=15,            # Maximum concurrent connections
                keepalive_expiry=150.0         # Connection TTL in seconds
            ),
            timeout=300.0
        )

    @with_retry(retry_config=JINA_RETRY_CONFIG, operation_name="_call_jina_reader_api")
    async def read_url(self, url: str, headers: Dict[str, str]) -> str:
        """
        Calls Jina Reader API (with retries) and returns the parsed web page for given URL.

        No need to add Authorization header in the argument, that will be added automatically in the final request.
        """
        authHeaders = {"Authorization": f"Bearer {self.jina_api_token}"}
        finalHeaders = {**headers, **authHeaders}
        async with self.pool.acquire_connection() as client:
            endpoint = f"{self.JINA_READER_API}{url}"
            response = await client.get(url=endpoint, headers=finalHeaders, timeout=self.API_TIMEOUT)
            response.raise_for_status()
            return response.text

    @with_retry(retry_config=JINA_RETRY_CONFIG, operation_name="_call_jina_search_api")
    async def search_query(self, query: str, headers: Dict[str, str]) -> str:
        """
        Calls Jina Reader API (with retries) and returns the parsed web page for given URL.

        No need to add Authorization header in the argument, that will be added automatically in the final request.
        """
        authHeaders = {"Authorization": f"Bearer {self.jina_api_token}"}
        finalHeaders = {**headers, **authHeaders}
        async with self.pool.acquire_connection() as client:
            endpoint = f"{self.JINA_SEARCH_API}{query}"
            response = await client.get(url=endpoint, headers=finalHeaders, timeout=self.API_TIMEOUT)
            response.raise_for_status()
            return response.text
