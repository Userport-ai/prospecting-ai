import asyncio
import json
import logging
import os
from datetime import datetime, timezone
from typing import Dict, Any, Optional
from utils.json_utils import JSONUtils

from google.cloud import bigquery
from google.oauth2 import service_account

logger = logging.getLogger(__name__)


class TaskResultManager:
    """
    Manages storing and retrieving final callback payloads for idempotent tasks
    in a dedicated BigQuery table named `enrichment_callbacks`.
    """

    def __init__(self):
        """Initialize BigQuery client and configuration."""
        service_account_path = os.getenv('GOOGLE_APPLICATION_CREDENTIALS')
        self.project = os.getenv('GOOGLE_CLOUD_PROJECT')

        if service_account_path and os.path.exists(service_account_path) and self.project:
            # Initialize credentials from service account file
            credentials = service_account.Credentials.from_service_account_file(
                service_account_path,
                scopes=["https://www.googleapis.com/auth/cloud-platform"]
            )

            # Initialize BigQuery client with explicit credentials
            self.client = bigquery.Client(
                credentials=credentials,
                project=self.project,
                location='US'
            )
        else:
            self.client = bigquery.Client(project=self.project,
                                          location='US')

        self.dataset = os.getenv('BIGQUERY_DATASET', 'userport_enrichment')
        # Prebuild the fully-qualified table ID for callbacks
        self.table_id = f"{self.project}.{self.dataset}.enrichment_callbacks"

    async def store_result(self, enrichment_type, callback_payload: Dict[str, Any]) -> None:
        """
        Inserts a new row into the enrichment_callbacks table with the entire
        callback payload (account_id, status, processed_data, etc.).
        """
        if (not callback_payload) or callback_payload.get("status", "unknown") != "completed":
            logger.info(f"Not storing the callback payload to bigquery, since the job didn't complete")
            return

        account_id = callback_payload.get("account_id")
        lead_id = callback_payload.get("lead_id")
        if not account_id:
            raise ValueError("callback_payload must contain 'account_id'")

        # Convert entire payload to JSON
        payload_json = json.dumps(callback_payload, default=JSONUtils.serialize_datetime)

        status = str(callback_payload.get("status", "unknown"))
        now_ts = datetime.now(timezone.utc).isoformat()

        row_to_insert = {
            "account_id": account_id,
            "lead_id": lead_id,
            "enrichment_type": enrichment_type,
            "status": status,
            "callback_payload": payload_json,
            "created_at": now_ts,
            "updated_at": now_ts
        }

        # Insert the row
        table_ref = self.client.get_table(self.table_id)
        errors = self.client.insert_rows_json(table_ref, [row_to_insert])
        if errors:
            logger.error(f"BigQuery insert errors: {errors}")

    async def get_result(self, enrichment_type: str, account_id: str, lead_id: Optional[str] = None) -> Optional[Dict[str, Any]]:
        """
        Retrieve the most recent callback payload for the given job/entity from
        the enrichment_callbacks table, returning it as a Python dict.

        If lead_id is provided (not None), it will be included in the WHERE clause.
        """
        # Base query with mandatory filters
        query = f"""
            SELECT callback_payload
            FROM `{self.table_id}`
            WHERE account_id = @account_id and
            enrichment_type = @enrichment_type
        """

        # Initialize query parameters with mandatory parameters
        query_parameters = [
            bigquery.ScalarQueryParameter("account_id", "STRING", account_id),
            bigquery.ScalarQueryParameter("enrichment_type", "STRING", enrichment_type),
        ]

        # Conditionally add lead_id filter
        if lead_id is not None:
            query += " AND lead_id = @lead_id"
            query_parameters.append(bigquery.ScalarQueryParameter("lead_id", "STRING", lead_id))

        # Append ordering and limit
        query += """
            ORDER BY updated_at DESC
            LIMIT 1
        """

        # Configure the query job with the parameters
        job_config = bigquery.QueryJobConfig(
            query_parameters=query_parameters
        )

        try:
            # Execute the query
            query_job = self.client.query(query, job_config=job_config)
            rows = list(query_job.result())

            # If no rows are returned, return None
            if not rows:
                logger.info(f"No rows found for account_id: {account_id}, lead_id: {lead_id} in enrichment_callbacks cache")
                return None

            row = rows[0]
            logger.debug(f"Retrieved row: {row}")

            # If callback_payload is empty or None, return None
            if not row.callback_payload:
                logger.info(f"No callback_payload found for account_id: {account_id}, lead_id: {lead_id}")
                return None

            # Determine the type of callback_payload and handle accordingly
            if isinstance(row.callback_payload, dict):
                return row.callback_payload
            elif isinstance(row.callback_payload, str):
                try:
                    payload = json.loads(row.callback_payload)
                    return payload
                except json.JSONDecodeError as jde:
                    logger.warning(f"Failed to parse callback_payload JSON: {jde}. callback_payload: {row.callback_payload}")
                    return None
            else:
                logger.warning(f"Unexpected type for callback_payload: {type(row.callback_payload)}. Value: {row.callback_payload}")
                return None

        except Exception as e:
            logger.error(f"Error querying BigQuery: {e}")
            logger.debug("Stack trace:", exc_info=True)
            return None

    async def resend_callback(self, callback_service, enrichment_type: str, account_id: str, lead_id: str) -> None:
        """
        Convenience method: fetch stored callback payload and re-send it
        through the callback service.
        """
        from utils.tracing import get_trace_context
        
        stored = await self.get_result(enrichment_type, account_id, lead_id)
        if not stored:
            raise ValueError(f"No stored callback payload for enrichment_type {enrichment_type}, account_id {account_id}, lead_id {lead_id}")

        # Extract just the fields that are expected by send_callback
        # This prevents errors when new fields are added to the callback service
        callback_params = {
            "job_id": stored.get("job_id"),
            "account_id": stored.get("account_id"),
            "lead_id": stored.get("lead_id"),
            "status": stored.get("status"),
            "enrichment_type": stored.get("enrichment_type"),
            "raw_data": stored.get("raw_data"),
            "processed_data": stored.get("processed_data"),
            "error_details": stored.get("error_details"),
            "source": stored.get("source", "jina_ai"),
            "is_partial": stored.get("is_partial", False),
            "completion_percentage": stored.get("completion_percentage", 100),
            "attempt_number": stored.get("attempt_number"),
            "max_retries": stored.get("max_retries"),
            "trace_id": stored.get("trace_id")
        }
        
        # Get the current trace context to include any information from the current execution
        current_context = get_trace_context()
        
        # Add trace_id from current context if not in stored result
        if current_context.get('trace_id') and not callback_params.get('trace_id'):
            callback_params['trace_id'] = current_context['trace_id']
        
        # Only include fields that actually have values
        callback_params = {k: v for k, v in callback_params.items() if v is not None}
        
        await callback_service.paginated_service.send_callback(**callback_params)
