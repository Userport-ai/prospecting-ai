import httpx
import asyncio
from utils.retry_utils import RetryableError
from contextlib import asynccontextmanager
from utils.loguru_setup import logger



class ConnectionPool:
    def __init__(self, limits=None, timeout=None):
        self._client = None
        self._lock = asyncio.Lock()
        self._active_connections = 0
        self.limits = limits or httpx.Limits(
            max_keepalive_connections=10,
            max_connections=20
        )
        self.timeout = timeout or 300.0

    @asynccontextmanager
    async def acquire_connection(self):
        """Acquire a connection from the pool."""
        async with self._lock:
            if self._active_connections >= self.limits.max_connections:
                logger.warning(f"Connection pool full ({self._active_connections}/{self.limits.max_connections})")
                raise RetryableError("Connection pool exhausted")

            if self._client is None or self._client.is_closed:
                self._client = httpx.AsyncClient(
                    limits=self.limits,
                    timeout=self.timeout
                )

            self._active_connections += 1
            logger.debug(f"Connection acquired. Active: {self._active_connections}")

        try:
            yield self._client
        finally:
            async with self._lock:
                self._active_connections -= 1
                logger.debug(f"Connection released. Active: {self._active_connections}")

    async def close(self):
        """Close all connections in the pool."""
        async with self._lock:
            if self._client and not self._client.is_closed:
                await self._client.aclose()
                self._client = None
            self._active_connections = 0

    @property
    def active_connections(self):
        return self._active_connections