import hashlib
import json
import logging
from datetime import datetime, timedelta
from typing import Dict, Any, Optional, Tuple
from google.cloud import bigquery

logger = logging.getLogger(__name__)

class APICacheService:
    """Service for caching external API requests and responses."""

    def __init__(self, client: bigquery.Client, project_id: str, dataset: str):
        """
        Initialize the cache service.

        Args:
            client: BigQuery client instance
            project_id: GCP project ID
            dataset: BigQuery dataset name
        """
        self.client = client
        self.project_id = project_id
        self.dataset = dataset
        self.table_name = "api_request_cache"
        self._ensure_cache_table()

    def _ensure_cache_table(self) -> None:
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

        results = list(self.client.query(query, job_config=job_config).result())

        if results:
            return {
                "data": results[0].response_data,
                "status_code": results[0].response_status
            }

        return None

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

        table = self.client.get_table(f"{self.project_id}.{self.dataset}.{self.table_name}")
        errors = self.client.insert_rows_json(table, [row])

        if errors:
            logger.error(f"Error caching response: {errors}")
            raise Exception(f"Failed to cache response: {errors}")

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
    Utility function to make a cached API request.

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
    import requests

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
                    "data": cached["data"]
                }
            )
            return cached["data"], cached["status_code"]

    logger.info(
        "Cache miss for request",
        extra={
            "url": url,
            "method": method,
            "tenant_id": tenant_id,
            "force_refresh": force_refresh
        }
    )

    # Make the actual API request
    response = requests.request(
        method=method,
        url=url,
        params=params,
        headers=headers,
        timeout=30
    )
    response_data = response.json() if response.content else {}
    
    # Log the response
    log_extra = {
        "url": url,
        "method": method,
        "tenant_id": tenant_id,
        "status_code": response.status_code,
        "response_size": len(response.content) if response.content else 0,
        "response": response_data
    }
    
    if response.status_code >= 400:
        logger.error(
            "API request failed",
            extra=log_extra
        )
    # else:
    #     logger.debug(
    #         "API request successful", 
    #         extra=log_extra
    #     )

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
