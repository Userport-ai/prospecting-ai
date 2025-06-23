import asyncio
import json
import os
from datetime import datetime, timezone
from typing import Dict, Any, Optional, List
from utils.json_utils import JSONUtils

from google.cloud import bigquery
from google.oauth2 import service_account
from utils.loguru_setup import logger


class TaskResultManager:
    """
    Manages storing and retrieving final callback payloads for idempotent tasks
    with support for large datasets through efficient batching.
    """

    # Configuration constants
    DEFAULT_BATCH_SIZE = 100  # Leads per batch
    BATCH_THRESHOLD = 50      # When to start batching
    MAX_CONCURRENT_INSERTS = 4  # Concurrent batch operations

    def __init__(self):
        """Initialize BigQuery client and configuration."""
        service_account_path = os.getenv('GOOGLE_APPLICATION_CREDENTIALS')
        self.project = os.getenv('GOOGLE_CLOUD_PROJECT')

        # Read batch configuration from environment
        self.batch_size = int(os.getenv('TASK_RESULT_BATCH_SIZE', self.DEFAULT_BATCH_SIZE))
        self.batch_threshold = int(os.getenv('TASK_RESULT_BATCH_THRESHOLD', self.BATCH_THRESHOLD))
        self.max_concurrent_inserts = int(os.getenv('TASK_RESULT_MAX_CONCURRENT', self.MAX_CONCURRENT_INSERTS))

        # Feature flag to enable/disable batching
        self.batching_enabled = os.getenv('ENABLE_RESULT_BATCHING', 'true').lower() == 'true'

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
            self.client = bigquery.Client(project=self.project, location='US')

        self.dataset = os.getenv('BIGQUERY_DATASET', 'userport_enrichment')
        # Prebuild the fully-qualified table ID for callbacks
        self.table_id = f"{self.project}.{self.dataset}.enrichment_callbacks"

        # Ensure the schema has required columns for batching
        self._ensure_schema_columns()

    async def _ensure_schema_columns(self):
        """
        Ensure the table has the required columns for batching.
        This only needs to be run once, but is safe to run multiple times.
        """
        try:
            # Get the current schema
            table = self.client.get_table(self.table_id)

            # Check if the required columns already exist
            has_is_batched = any(field.name == 'is_batched' for field in table.schema)
            has_batch_info = any(field.name == 'batch_info' for field in table.schema)

            if has_is_batched and has_batch_info:
                # Schema is already updated
                return

            # Need to update schema
            schema_updates = []
            if not has_is_batched:
                schema_updates.append(bigquery.SchemaField("is_batched", "BOOLEAN"))
            if not has_batch_info:
                schema_updates.append(bigquery.SchemaField("batch_info", "JSON"))

            if schema_updates:
                # Add new columns to the existing schema
                new_schema = list(table.schema) + schema_updates
                table.schema = new_schema
                # Update the table
                self.client.update_table(table, ["schema"])
                logger.info(f"Updated schema for {self.table_id} to support batching")

        except Exception as e:
            logger.warning(f"Could not ensure schema columns: {str(e)}")
            # Continue anyway - schema updates can be done manually if needed

    async def store_result(self, enrichment_type: str, callback_payload: Dict[str, Any]) -> None:
        """
        Public API: Stores the callback payload, automatically handling large datasets.
        This maintains the same signature for backward compatibility.
        """
        if (not callback_payload) or callback_payload.get("status", "unknown") != "completed":
            logger.info(f"Not storing the callback payload to bigquery, since the job didn't complete")
            return

        account_id = callback_payload.get("account_id")
        lead_id = callback_payload.get("lead_id")
        if not account_id:
            raise ValueError("callback_payload must contain 'account_id'")

        # Check if this payload needs batching
        if self.batching_enabled:
            # Check for large arrays that might cause timeouts
            processed_data = callback_payload.get("processed_data", {})
            structured_leads = processed_data.get("structured_leads", [])
            qualified_leads = processed_data.get("qualified_leads", [])
            all_leads = processed_data.get("all_leads", [])

            # Find the largest leads array
            largest_leads_count = max(
                len(structured_leads),
                len(qualified_leads),
                len(all_leads)
            )

            if largest_leads_count >= self.batch_threshold:
                logger.info(f"Using batched storage for large dataset ({largest_leads_count} leads)")
                await self._store_result_batched(enrichment_type, callback_payload)
                return

        # Standard storage path for smaller payloads or when batching is disabled
        await self._store_result_standard(enrichment_type, callback_payload)

    async def _store_result_standard(self, enrichment_type: str, callback_payload: Dict[str, Any]) -> None:
        """
        Internal method: Standard storage for normal-sized payloads.
        """
        try:
            account_id = callback_payload.get("account_id")
            lead_id = callback_payload.get("lead_id")

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
                "updated_at": now_ts,
                "is_batched": False,  # Explicitly mark as not batched
                "batch_info": None    # No batch info needed
            }

            # Insert the row
            table_ref = self.client.get_table(self.table_id)
            errors = self.client.insert_rows_json(table_ref, [row_to_insert])
            if errors:
                logger.error(f"BigQuery insert errors: {errors}")
        except Exception as e:
            logger.error(f"Error storing standard result: {str(e)}", exc_info=True)

    async def _store_result_batched(self, enrichment_type: str, callback_payload: Dict[str, Any]) -> None:
        """
        Internal method: Batched storage for large payloads.
        This splits the data into a master record and batch records.
        """
        try:
            account_id = callback_payload.get("account_id")
            lead_id = callback_payload.get("lead_id")
            job_id = callback_payload.get("job_id", "unknown")

            # Extract arrays that might be large
            processed_data = callback_payload.get("processed_data", {}).copy()
            structured_leads = processed_data.pop("structured_leads", []) if "structured_leads" in processed_data else []
            qualified_leads = processed_data.pop("qualified_leads", []) if "qualified_leads" in processed_data else []
            all_leads = processed_data.pop("all_leads", []) if "all_leads" in processed_data else []

            # Create master record with metadata but without the large arrays
            master_payload = callback_payload.copy()
            master_payload["processed_data"] = processed_data

            # Add metadata about batched data
            batch_info = {
                "is_master": True,
                "job_id": job_id,
                "data_types": {},
                "created_at": datetime.now(timezone.utc).isoformat()
            }

            # Add info for each data type that has leads
            if structured_leads:
                batch_info["data_types"]["structured_leads"] = {
                    "count": len(structured_leads),
                    "batches": (len(structured_leads) + self.batch_size - 1) // self.batch_size,
                    "batch_size": self.batch_size
                }

            if qualified_leads:
                batch_info["data_types"]["qualified_leads"] = {
                    "count": len(qualified_leads),
                    "batches": (len(qualified_leads) + self.batch_size - 1) // self.batch_size,
                    "batch_size": self.batch_size
                }

            if all_leads:
                batch_info["data_types"]["all_leads"] = {
                    "count": len(all_leads),
                    "batches": (len(all_leads) + self.batch_size - 1) // self.batch_size,
                    "batch_size": self.batch_size
                }

            # Store the master record
            now_ts = datetime.now(timezone.utc).isoformat()
            master_row = {
                "account_id": account_id,
                "lead_id": lead_id,
                "enrichment_type": enrichment_type,
                "status": str(callback_payload.get("status", "unknown")),
                "callback_payload": json.dumps(master_payload, default=JSONUtils.serialize_datetime),
                "created_at": now_ts,
                "updated_at": now_ts,
                "is_batched": True,  # Mark as batched
                "batch_info": json.dumps(batch_info)  # Store batch metadata
            }

            # Insert master record
            table_ref = self.client.get_table(self.table_id)
            errors = self.client.insert_rows_json(table_ref, [master_row])
            if errors:
                logger.error(f"BigQuery insert errors for master record: {errors}")
                return

            # Process each data type with batching
            batch_tasks = []
            semaphore = asyncio.Semaphore(self.max_concurrent_inserts)

            # Create batch processing function
            async def process_batch(data_type, data_array, batch_idx):
                async with semaphore:
                    try:
                        batch_start = batch_idx * self.batch_size
                        batch_end = min(batch_start + self.batch_size, len(data_array))
                        batch = data_array[batch_start:batch_end]

                        # Create batch record
                        batch_info = {
                            "is_master": False,
                            "job_id": job_id,
                            "data_type": data_type,
                            "batch_index": batch_idx,
                            "total_batches": (len(data_array) + self.batch_size - 1) // self.batch_size,
                            "start_index": batch_start,
                            "end_index": batch_end,
                            "items_count": len(batch)
                        }

                        # Only store the batch data in the payload
                        batch_payload = {
                            "job_id": job_id,
                            "data": batch
                        }

                        # Use a unique enrichment type for each batch for easy querying
                        batch_enrichment_type = f"{enrichment_type}_{data_type}_batch_{batch_idx}"

                        batch_row = {
                            "account_id": account_id,
                            "lead_id": lead_id,
                            "enrichment_type": batch_enrichment_type,
                            "status": "batch",
                            "callback_payload": json.dumps(batch_payload, default=JSONUtils.serialize_datetime),
                            "created_at": now_ts,
                            "updated_at": now_ts,
                            "is_batched": True,
                            "batch_info": json.dumps(batch_info)
                        }

                        # Create a new client for each batch to avoid connection issues
                        batch_client = bigquery.Client(project=self.project, location='US')
                        batch_table = batch_client.get_table(self.table_id)

                        batch_errors = batch_client.insert_rows_json(batch_table, [batch_row])
                        if batch_errors:
                            logger.error(f"BigQuery insert errors for {data_type} batch {batch_idx}: {batch_errors}")

                        # Small delay to avoid overwhelming connections
                        await asyncio.sleep(0.1)
                    except Exception as e:
                        logger.error(f"Error processing {data_type} batch {batch_idx}: {str(e)}", exc_info=True)

            # Create batch tasks for each data type
            if structured_leads:
                for i in range(0, (len(structured_leads) + self.batch_size - 1) // self.batch_size):
                    batch_tasks.append(process_batch("structured_leads", structured_leads, i))

            if qualified_leads:
                for i in range(0, (len(qualified_leads) + self.batch_size - 1) // self.batch_size):
                    batch_tasks.append(process_batch("qualified_leads", qualified_leads, i))

            if all_leads:
                for i in range(0, (len(all_leads) + self.batch_size - 1) // self.batch_size):
                    batch_tasks.append(process_batch("all_leads", all_leads, i))

            # Execute all batch tasks concurrently (with controlled concurrency)
            if batch_tasks:
                await asyncio.gather(*batch_tasks)
                logger.info(f"Successfully stored {len(batch_tasks)} batches for job {job_id}")

        except Exception as e:
            logger.error(f"Error in batched storage: {str(e)}", exc_info=True)

    async def get_result(self, enrichment_type: str, account_id: str, lead_id: Optional[str] = None) -> Optional[Dict[str, Any]]:
        """
        Public API: Retrieve the most recent callback payload.
        Automatically handles reconstruction of batched data.
        """
        try:
            # First get the master record
            master_record = await self._get_master_record(enrichment_type, account_id, lead_id)
            if not master_record:
                logger.info(f"No record found for enrichment_type={enrichment_type}, account_id={account_id}, lead_id={lead_id}")
                return None

            # Parse the callback payload if needed
            callback_payload = master_record.get("callback_payload")
            if isinstance(callback_payload, str):
                try:
                    callback_payload = json.loads(callback_payload)
                except json.JSONDecodeError:
                    logger.warning(f"Could not parse callback_payload JSON")
                    return None

            # Check if this is a batched record
            is_batched = master_record.get("is_batched", False)
            if not is_batched:
                # Not batched, return the payload directly
                return callback_payload

            # This is a batched record, we need to reassemble it
            batch_info = master_record.get("batch_info")
            if isinstance(batch_info, str):
                try:
                    batch_info = json.loads(batch_info)
                except json.JSONDecodeError:
                    logger.warning(f"Could not parse batch_info JSON")
                    return callback_payload  # Return what we have

            # If not a master record or missing batch info, return what we have
            if not batch_info or not batch_info.get("is_master", False):
                return callback_payload

            # Reconstruct the full payload from batches
            job_id = batch_info.get("job_id")
            if not job_id:
                logger.warning(f"Batched record missing job_id")
                return callback_payload

            # Rehydrate the leads for each data type
            processed_data = callback_payload.get("processed_data", {})
            data_types = batch_info.get("data_types", {})

            # For each data type, fetch and combine all batches
            for data_type, type_info in data_types.items():
                if type_info.get("count", 0) > 0:
                    leads = await self._fetch_batched_data(
                        enrichment_type=enrichment_type,
                        data_type=data_type,
                        job_id=job_id,
                        account_id=account_id,
                        lead_id=lead_id,
                        total_batches=type_info.get("batches", 1)
                    )
                    processed_data[data_type] = leads

            # Update the payload with the reassembled data
            callback_payload["processed_data"] = processed_data
            return callback_payload

        except Exception as e:
            logger.error(f"Error retrieving result: {str(e)}", exc_info=True)
            return None

    async def _get_master_record(self, enrichment_type: str, account_id: str, lead_id: Optional[str] = None) -> Optional[Dict[str, Any]]:
        """
        Internal method: Fetch the master record.
        Works with both batched and non-batched records.
        """
        query = f"""
            SELECT callback_payload, is_batched, batch_info
            FROM `{self.table_id}`
            WHERE account_id = @account_id AND
                  enrichment_type = @enrichment_type
        """

        params = [
            bigquery.ScalarQueryParameter("account_id", "STRING", account_id),
            bigquery.ScalarQueryParameter("enrichment_type", "STRING", enrichment_type),
        ]

        if lead_id is not None:
            query += " AND lead_id = @lead_id"
            params.append(bigquery.ScalarQueryParameter("lead_id", "STRING", lead_id))

        # Get the most recent record
        query += """
            ORDER BY updated_at DESC
            LIMIT 1
        """

        try:
            job_config = bigquery.QueryJobConfig(query_parameters=params)
            query_job = self.client.query(query, job_config=job_config)
            rows = list(query_job.result())

            if not rows:
                logger.info(f"No rows found for account_id: {account_id}, lead_id: {lead_id}")
                return None

            row = rows[0]
            result = {
                "callback_payload": row.callback_payload,
                "is_batched": row.is_batched
            }

            # Add batch_info if it exists
            if hasattr(row, 'batch_info') and row.batch_info:
                result["batch_info"] = row.batch_info

            return result

        except Exception as e:
            logger.error(f"Error getting master record: {str(e)}", exc_info=True)
            return None

    async def _fetch_batched_data(
            self,
            enrichment_type: str,
            data_type: str,
            job_id: str,
            account_id: str,
            lead_id: Optional[str],
            total_batches: int
    ) -> List[Dict[str, Any]]:
        """
        Internal method: Fetch and combine all batches for a data type.
        """
        all_data = []

        # Build query to get all batch components
        query = f"""
            SELECT batch_info, callback_payload
            FROM `{self.table_id}`
            WHERE account_id = @account_id AND
                  is_batched = TRUE AND
                  enrichment_type LIKE @batch_pattern AND
                  JSON_EXTRACT(batch_info, '$.job_id') = @job_id AND
                  JSON_EXTRACT(batch_info, '$.data_type') = @data_type
        """

        params = [
            bigquery.ScalarQueryParameter("account_id", "STRING", account_id),
            bigquery.ScalarQueryParameter("batch_pattern", "STRING", f"{enrichment_type}_{data_type}_batch_%"),
            bigquery.ScalarQueryParameter("job_id", "STRING", job_id),
            bigquery.ScalarQueryParameter("data_type", "STRING", data_type),
        ]

        if lead_id is not None:
            query += " AND lead_id = @lead_id"
            params.append(bigquery.ScalarQueryParameter("lead_id", "STRING", lead_id))

        # Order by batch index
        query += """
            ORDER BY CAST(JSON_EXTRACT(batch_info, '$.batch_index') AS INT64)
        """

        try:
            job_config = bigquery.QueryJobConfig(query_parameters=params)
            query_job = self.client.query(query, job_config=job_config)
            rows = list(query_job.result())

            # Process batch results
            batch_data = {}  # Map of batch_index -> data

            for row in rows:
                # Parse batch_info to get the index
                if not row.batch_info:
                    continue

                batch_info = self._parse_json(row.batch_info)
                if not batch_info:
                    continue

                batch_index = batch_info.get("batch_index")
                if batch_index is None:
                    continue

                # Parse the payload to get the data
                payload = self._parse_json(row.callback_payload)
                if not payload or "data" not in payload:
                    continue

                # Store in map by index
                batch_data[batch_index] = payload["data"]

            # Combine all batches in proper order
            for i in range(total_batches):
                if i in batch_data:
                    all_data.extend(batch_data[i])

            return all_data

        except Exception as e:
            logger.error(f"Error fetching batched data: {str(e)}", exc_info=True)
            return []

    def _parse_json(self, json_data):
        """Helper method to safely parse JSON string or return object as is."""
        if isinstance(json_data, str):
            try:
                return json.loads(json_data)
            except json.JSONDecodeError:
                return None
        elif isinstance(json_data, dict):
            return json_data
        else:
            return None

    async def resend_callback(self, callback_service, enrichment_type: str, account_id: str, lead_id: str) -> None:
        """
        Convenience method: fetch stored callback payload and re-send it
        through the callback service.
        """
        stored = await self.get_result(enrichment_type, account_id, lead_id)
        if not stored:
            raise ValueError(f"No stored callback payload for enrichment_type: {enrichment_type}, account_id: {account_id}, lead_id: {lead_id}")

        await callback_service.paginated_service.send_callback(**stored)