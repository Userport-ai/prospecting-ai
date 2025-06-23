import hashlib
import json
from datetime import datetime, timedelta, timezone
from typing import Dict, Any, Optional, List, Union

from google.cloud import bigquery

from utils.async_utils import to_thread
from utils.token_usage import TokenUsage
from utils.loguru_setup import logger
from json_repair import repair_json


class AICacheService:
    """Service for caching AI prompts and responses."""

    def __init__(self, client: bigquery.Client, project_id: str, dataset: str):
        """Initialize the AI cache service."""
        self.client = client
        self.project_id = project_id
        self.dataset = dataset
        self.table_name = "ai_prompt_cache"

    # This will be called when a task is created to ensure that the cache table always exists
    @to_thread
    def ensure_cache_table(self) -> None:
        """Create the cache table if it doesn't exist."""
        schema = [
            bigquery.SchemaField("cache_key", "STRING", mode="REQUIRED"),
            bigquery.SchemaField("provider", "STRING", mode="REQUIRED"),
            bigquery.SchemaField("model", "STRING", mode="REQUIRED"),
            bigquery.SchemaField("prompt", "STRING", mode="REQUIRED"),
            bigquery.SchemaField("is_json_response", "BOOLEAN", mode="REQUIRED"),
            bigquery.SchemaField("operation_tag", "STRING"),
            bigquery.SchemaField("temperature", "FLOAT"),  # Add temperature to schema
            bigquery.SchemaField("response_data", "JSON"),
            bigquery.SchemaField("response_text", "STRING"),
            bigquery.SchemaField("prompt_tokens", "INTEGER"),
            bigquery.SchemaField("completion_tokens", "INTEGER"),
            bigquery.SchemaField("total_tokens", "INTEGER"),
            bigquery.SchemaField("total_cost_in_usd", "FLOAT64"),
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

    def _generate_cache_key(
            self,
            prompt: str,
            provider: str,
            model: str,
            is_json: bool,
            operation_tag: str,
            temperature: Optional[float] = None
    ) -> str:
        """Generate a unique cache key for the AI request including temperature."""
        cache_data = {
            'prompt': prompt,
            'provider': provider,
            'model': model,
            'is_json': is_json,
            'operation_tag': operation_tag,
            'temperature': temperature  # Include temperature in cache key
        }
        cache_str = json.dumps(cache_data, sort_keys=True)
        return hashlib.sha256(cache_str.encode()).hexdigest()

    async def get_cached_response(
            self,
            prompt: str,
            provider: str,
            model: str,
            is_json: bool = True,
            operation_tag: str = "default",
            tenant_id: Optional[str] = None,
            temperature: Optional[float] = None
    ) -> Optional[Dict[str, Any]]:
        """Get cached response for the given AI prompt."""
        cache_key = self._generate_cache_key(prompt, provider, model, is_json, operation_tag, temperature)

        query = f"""
        SELECT 
            response_data,
            response_text,
            prompt_tokens,
            completion_tokens,
            total_tokens,
            total_cost_in_usd
        FROM `{self.project_id}.{self.dataset}.{self.table_name}`
        WHERE cache_key = @cache_key
        AND provider = @provider
        AND model = @model
        AND is_json_response = @is_json
        AND (temperature IS NULL OR temperature = @temperature)
        AND (expires_at IS NULL OR expires_at > CURRENT_TIMESTAMP())
        AND (tenant_id IS NULL OR tenant_id = @tenant_id)
        ORDER BY created_at DESC
        LIMIT 1
        """

        job_config = bigquery.QueryJobConfig(
            query_parameters=[
                bigquery.ScalarQueryParameter("cache_key", "STRING", cache_key),
                bigquery.ScalarQueryParameter("provider", "STRING", provider),
                bigquery.ScalarQueryParameter("model", "STRING", model),
                bigquery.ScalarQueryParameter("is_json", "BOOL", is_json),
                bigquery.ScalarQueryParameter("tenant_id", "STRING", tenant_id),
                bigquery.ScalarQueryParameter("temperature", "FLOAT", temperature)
            ]
        )

        # Execute query in a separate thread
        results = await self._execute_query(query, job_config)
        if results:
            row = results[0]

            # Create token usage object
            token_usage = TokenUsage(
                operation_tag=operation_tag,
                prompt_tokens=row.prompt_tokens,
                completion_tokens=row.completion_tokens,
                total_tokens=row.total_tokens,
                total_cost_in_usd=row.total_cost_in_usd,
                provider=provider
            )

            # Parse the response based on type
            content = None
            if is_json:
                # BigQuery client already deserializes JSON fields
                content = row.response_data
                if content is not None:
                    if (isinstance(content, dict) and not content) or \
                            (isinstance(content, list) and not content) or \
                            content == '':
                        logger.debug(f"Skipping cached response with empty JSON content for key: {cache_key}")
                        return None
            else:
                content = row.response_text
                if not content or content.strip() == '':
                    logger.debug(f"Skipping cached response with empty text content for key: {cache_key}")
                    return None

            return {
                "content": content,
                "token_usage": token_usage
            }
        return None

    @to_thread
    def _execute_query(self, query: str, job_config: bigquery.QueryJobConfig) -> List[Any]:
        """Execute a BigQuery query in a separate thread and return results"""
        return list(self.client.query(query, job_config=job_config).result())

    def _log_response_structure(self, response_data: Any) -> None:
        """Log detailed structure of response data including types of all values."""
        if not isinstance(response_data, dict):
            logger.debug(f"Response data is not a dict, type: {type(response_data)}")
            return

        # Log first-level keys and their value types
        type_info = {
            key: f"{type(value).__name__} ({len(value) if isinstance(value, (list, dict, str)) else 'N/A'})"
            for key, value in response_data.items()
        }
        logger.debug(f"Response data structure: {type_info}")

        # For nested structures, log more details
        for key, value in response_data.items():
            if isinstance(value, list) and value:
                # Log type of first item in list
                first_item = value[0]
                if isinstance(first_item, dict):
                    nested_types = {
                        nested_key: type(nested_value).__name__
                        for nested_key, nested_value in first_item.items()
                    }
                    logger.debug(f"First item in '{key}' list has structure: {nested_types}")
                else:
                    logger.debug(f"Items in '{key}' list are of type: {type(first_item).__name__}")
            elif isinstance(value, dict):
                nested_types = {
                    nested_key: type(nested_value).__name__
                    for nested_key, nested_value in value.items()
                }
                logger.debug(f"Nested structure for '{key}': {nested_types}")

    async def cache_response(
            self,
            prompt: str,
            response: Union[Dict[str, Any], str],
            token_usage: TokenUsage,
            provider: str,
            model: str,
            is_json: bool = True,
            operation_tag: str = "default",
            tenant_id: Optional[str] = None,
            ttl_hours: Optional[int] = None,
            temperature: Optional[float] = None
    ) -> None:

        # Skip caching for empty responses
        if is_json and (not response or response == {}):
            logger.warning(f"Skipping cache for empty JSON response for prompt: {prompt[:100]}...")
            return

        if not is_json and (not response or response == ""):
            logger.warning(f"Skipping cache for empty text response for prompt: {prompt[:100]}...")
            return

        # Skip caching responses with error indicators
        if is_json and isinstance(response, dict) and ("error" in response or "refusal" in response):
            logger.warning(f"Skipping cache for response with error/refusal: {str(response)[:100]}...")
            return

        # Generate cache key
        cache_key = self._generate_cache_key(prompt, provider, model, is_json, operation_tag, temperature)
        expires_at = None

        if ttl_hours is not None:
            expires_at = datetime.now(timezone.utc) + timedelta(hours=ttl_hours)

        response_data = None
        response_text = None

        try:
            if isinstance(response, dict):
                # First try standard JSON serialization
                response_data = json.dumps(response, ensure_ascii=False)
            else:
                # For non-dict responses, wrap in a dict
                response_data = json.dumps({"data": str(response)}, ensure_ascii=False)
        except Exception as e:
            logger.warning(f"JSON serialization failed, attempting repair: {str(e)}")
            response_data = repair_json(str(response), ensure_ascii=False)

        row = {
            "cache_key": cache_key,
            "provider": provider,
            "model": model,
            "prompt": prompt,
            "is_json_response": is_json,
            "operation_tag": operation_tag,
            "temperature": temperature,  # Store temperature value
            "response_data": response_data,  # Already JSON string
            "response_text": response_text,
            "prompt_tokens": token_usage.prompt_tokens,
            "completion_tokens": token_usage.completion_tokens,
            "total_tokens": token_usage.total_tokens,
            "total_cost_in_usd": token_usage.total_cost_in_usd,
            "created_at": datetime.now(timezone.utc).isoformat(),
            "expires_at": expires_at.isoformat() if expires_at else None,
            "tenant_id": tenant_id
        }

        # For debugging
        logger.debug(f"Inserting row with response_data type: {type(row['response_data'])}")

        # Insert row in a separate thread
        errors = await self._insert_row(row)

        if errors:
            logger.error(f"Error caching AI response: {errors}")
            logger.error(f"Failed row data: {json.dumps(row, default=str)}")
            raise Exception(f"Failed to cache AI response: {errors}")

    @to_thread
    def _insert_row(self, row: Dict[str, Any]) -> List[Any]:
        """Insert a row into the cache table in a separate thread"""
        table = self.client.get_table(f"{self.project_id}.{self.dataset}.{self.table_name}")
        return self.client.insert_rows_json(table, [row])

    async def clear_expired_cache(self, days: int = 30) -> int:
        """Clear expired cache entries and entries older than specified days."""
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