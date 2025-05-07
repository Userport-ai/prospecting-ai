import hashlib
import json
from datetime import datetime, timedelta
from typing import Dict, Any, Optional, Tuple, List

import httpx
from google.cloud import bigquery

from services.bigquery_service import BigQueryService
from utils.connection_pool import ConnectionPool
from utils.async_utils import to_thread
from utils.loguru_setup import logger




class APICacheService:
    """Service for caching external API requests and responses."""

    def __init__(self, bq_service: Optional[BigQueryService] = None, 
                 client: Optional[bigquery.Client] = None, 
                 project_id: Optional[str] = None, 
                 dataset: Optional[str] = None,
                 connection_pool: Optional[ConnectionPool] = None):
        """
        Initialize the cache service.

        Args:
            bq_service: BigQuery service instance (preferred way to initialize)
            client: BigQuery client instance (alternative to bq_service)
            project_id: GCP project ID (alternative to bq_service)
            dataset: BigQuery dataset name (alternative to bq_service)
            connection_pool: Optional connection pool to use for HTTP requests
        """
        if bq_service is not None:
            # Initialize from BigQueryService
            self.client = bq_service.client
            self.project_id = bq_service.project
            self.dataset = bq_service.dataset
        elif client is not None and project_id is not None and dataset is not None:
            # Initialize from individual parameters
            self.client = client
            self.project_id = project_id
            self.dataset = dataset
        else:
            raise ValueError("Either bq_service or (client, project_id, dataset) must be provided")
            
        self.table_name = "api_request_cache"

        # Use provided connection pool or create a new one
        self.connection_pool = connection_pool or ConnectionPool(
            limits=httpx.Limits(max_keepalive_connections=10, max_connections=20),
            timeout=30.0
        )

    async def close(self) -> None:
        """Close the connection pool to free resources."""
        await self.connection_pool.close()

    @to_thread
    def ensure_cache_table(self) -> None:
        """Create the cache table if it doesn't exist."""
        schema = [
            bigquery.SchemaField("cache_key", "STRING", mode="REQUIRED"),
            bigquery.SchemaField("request_method", "STRING", mode="REQUIRED"),
            bigquery.SchemaField("request_url", "STRING", mode="REQUIRED"),
            bigquery.SchemaField("request_params", "JSON"),
            bigquery.SchemaField("request_headers", "JSON"),
            bigquery.SchemaField("response_data", "JSON"),
            bigquery.SchemaField("response_status", "INTEGER"),
            bigquery.SchemaField("created_at", "TIMESTAMP", mode="REQUIRED"),
            bigquery.SchemaField("expires_at", "TIMESTAMP"),
            bigquery.SchemaField("tenant_id", "STRING"),
        ]

        table_id = f"{self.project_id}.{self.dataset}.{self.table_name}"

        try:
            self.client.get_table(table_id)
        except Exception:
            table = bigquery.Table(table_id, schema=schema)
            table = self.client.create_table(table)
            logger.info(f"Created table {table_id}")

    def _generate_cache_key(self, url: str, params: Dict[str, Any], headers: Dict[str, Any]) -> str:
        """Generate a unique cache key for the request."""
        # Remove authentication headers from cache key generation
        cache_headers = headers.copy()
        cache_headers.pop('Authorization', None)
        cache_headers.pop('api-key', None)
        cache_headers.pop('x-api-key', None)

        # Create a string combining all relevant request data
        cache_data = {
            'url': url,
            'params': params,
            'headers': cache_headers
        }

        # Generate SHA-256 hash
        cache_str = json.dumps(cache_data, sort_keys=True)
        return hashlib.sha256(cache_str.encode()).hexdigest()

    async def get_cached_response(
            self,
            url: str,
            method: str = "GET",
            params: Optional[Dict[str, Any]] = None,
            headers: Optional[Dict[str, Any]] = None,
            tenant_id: Optional[str] = None
    ) -> Optional[Dict[str, Any]]:
        """
        Get cached response for the given API request.

        Args:
            url: Request URL
            method: HTTP method
            params: Request parameters
            headers: Request headers
            tenant_id: Optional tenant ID for multi-tenancy

        Returns:
            Cached response if found and valid, None otherwise
        """
        params = params or {}
        headers = headers or {}

        cache_key = self._generate_cache_key(url, params, headers)

        query = f"""
        SELECT response_data, response_status
        FROM `{self.project_id}.{self.dataset}.{self.table_name}`
        WHERE cache_key = @cache_key
        AND (expires_at IS NULL OR expires_at > CURRENT_TIMESTAMP())
        AND (tenant_id IS NULL OR tenant_id = @tenant_id)
        ORDER BY created_at DESC
        LIMIT 1
        """

        job_config = bigquery.QueryJobConfig(
            query_parameters=[
                bigquery.ScalarQueryParameter("cache_key", "STRING", cache_key),
                bigquery.ScalarQueryParameter("tenant_id", "STRING", tenant_id)
            ]
        )

        # Execute query in a separate thread to avoid blocking the event loop
        results = await self._execute_query(query, job_config)

        if results:
            return {
                "data": results[0].response_data,
                "status_code": results[0].response_status
            }

        return None

    @to_thread
    def _execute_query(self, query: str, job_config: bigquery.QueryJobConfig) -> List[Any]:
        """Execute a BigQuery query in a separate thread and return results"""
        return list(self.client.query(query, job_config=job_config).result())

    async def cache_response(
            self,
            url: str,
            response_data: Dict[str, Any],
            status_code: int,
            method: str = "GET",
            params: Optional[Dict[str, Any]] = None,
            headers: Optional[Dict[str, Any]] = None,
            tenant_id: Optional[str] = None,
            ttl_hours: Optional[int] = None
    ) -> None:
        """
        Cache an API response.

        Args:
            url: Request URL
            response_data: Response data to cache
            status_code: Response status code
            method: HTTP method
            params: Request parameters
            headers: Request headers
            tenant_id: Optional tenant ID
            ttl_hours: Cache TTL in hours (None for no expiration)
        """
        params = params or {}
        headers = headers or {}

        cache_key = self._generate_cache_key(url, params, headers)
        expires_at = None

        if ttl_hours is not None:
            expires_at = datetime.utcnow() + timedelta(hours=ttl_hours)

        row = {
            "cache_key": cache_key,
            "request_method": method,
            "request_url": url,
            "request_params": json.dumps(params),
            "request_headers": json.dumps(headers),
            "response_data": json.dumps(response_data),
            "response_status": status_code,
            "created_at": datetime.utcnow().isoformat(),
            "expires_at": expires_at.isoformat() if expires_at else None,
            "tenant_id": tenant_id
        }

        # Insert row in a separate thread
        errors = await self._insert_row(row)

        if errors:
            logger.error(f"Error caching response: {errors}")
            raise Exception(f"Failed to cache response: {errors}")

    @to_thread
    def _insert_row(self, row: Dict[str, Any]) -> List[Any]:
        """Insert a row into the cache table in a separate thread"""
        table = self.client.get_table(f"{self.project_id}.{self.dataset}.{self.table_name}")
        return self.client.insert_rows_json(table, [row])

    async def clear_expired_cache(self, days: int = 30) -> int:
        """
        Clear expired cache entries and entries older than specified days.

        Args:
            days: Age in days for cache cleanup

        Returns:
            Number of entries cleared
        """
        query = f"""
        DELETE FROM `{self.project_id}.{self.dataset}.{self.table_name}`
        WHERE expires_at < CURRENT_TIMESTAMP()
        OR created_at < TIMESTAMP_SUB(CURRENT_TIMESTAMP(), INTERVAL @days DAY)
        """

        job_config = bigquery.QueryJobConfig(
            query_parameters=[
                bigquery.ScalarQueryParameter("days", "INTEGER", days)
            ]
        )

        # Execute delete query in a separate thread
        return await self._execute_delete_query(query, job_config)

    @to_thread
    def _execute_delete_query(self, query: str, job_config: bigquery.QueryJobConfig) -> int:
        """Execute a delete query in a separate thread and return affected rows"""
        query_job = self.client.query(query, job_config=job_config)
        query_job.result()
        return query_job.num_dml_affected_rows


async def cached_request(
        cache_service: APICacheService,
        url: str,
        method: str = "GET",
        params: Optional[Dict[str, Any]] = None,
        headers: Optional[Dict[str, Any]] = None,
        tenant_id: Optional[str] = None,
        ttl_hours: Optional[int] = 24,
        force_refresh: bool = False
) -> Tuple[Dict[str, Any], int]:
    """
    Utility function to make a cached API request asynchronously.

    Args:
        cache_service: APICacheService instance
        url: Request URL
        method: HTTP method
        params: Request parameters
        headers: Request headers
        tenant_id: Optional tenant ID
        ttl_hours: Cache TTL in hours
        force_refresh: Force a new request ignoring cache

    Returns:
        Tuple of (response_data, status_code)
    """
    if not force_refresh:
        cached = await cache_service.get_cached_response(
            url=url,
            method=method,
            params=params,
            headers=headers,
            tenant_id=tenant_id
        )

        if cached:
            logger.info(
                "Cache hit for request",
                extra={
                    "url": url,
                    "method": method,
                    "tenant_id": tenant_id,
                    "status_code": cached["status_code"],
                }
            )
            return cached["data"], cached["status_code"]

    logger.info(
        "Cache miss for request",
        extra={
            "url": url,
            "method": method,
            "params": params,
            "tenant_id": tenant_id,
            "force_refresh": force_refresh
        }
    )

    # Make the actual API request asynchronously using the connection pool
    try:
        async with cache_service.connection_pool.acquire_connection() as client:
            response = await client.request(
                method=method,
                url=url,
                params=params,
                headers=headers,
            )

            response_data = response.json() if response.content else {}

            # Log the response
            log_extra = {
                "url": url,
                "method": method,
                "tenant_id": tenant_id,
                "status_code": response.status_code,
                "response_size": len(response.content) if response.content else 0,
            }

            if response.status_code >= 400:
                log_extra["response"] = response_data
                logger.error(
                    "API request failed",
                    extra=log_extra
                )
            else:
                logger.debug(
                    "API request successful",
                    extra=log_extra
                )

            # Cache successful responses
            if response.status_code < 400:
                await cache_service.cache_response(
                    url=url,
                    response_data=response_data,
                    status_code=response.status_code,
                    method=method,
                    params=params,
                    headers=headers,
                    tenant_id=tenant_id,
                    ttl_hours=ttl_hours
                )

            return response_data, response.status_code
    except Exception as e:
        logger.error(f"Error making request to {url}: {str(e)}")
        raise
