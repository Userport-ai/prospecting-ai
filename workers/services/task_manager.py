import json
import os
from datetime import datetime
from typing import Dict, Any, List, Optional

from google.cloud import tasks_v2

from .bigquery_service import BigQueryService  # Import BigQueryService for reuse


class TaskManager:
    """Manager for Cloud Tasks operations and job tracking."""

    def __init__(self, bigquery_service: BigQueryService = None):
        """
        Initialize TaskManager with Cloud Tasks configuration.

        Args:
            bigquery_service: Optional BigQueryService instance for database operations.
                            If not provided, a new instance will be created.
        """
        # Cloud Tasks configuration
        self.client = tasks_v2.CloudTasksClient()
        self.project = os.getenv('GOOGLE_CLOUD_PROJECT')
        self.queue = os.getenv('CLOUD_TASKS_QUEUE')
        self.location = os.getenv('CLOUD_TASKS_LOCATION', 'us-west1')
        self.base_url = os.getenv('WORKER_BASE_URL')
        self.service_account_email = os.getenv('CLOUD_TASKS_SERVICE_ACCOUNT_EMAIL')

        # BigQuery operations handler
        self.bq_service = bigquery_service or BigQueryService()

    def _get_queue_path(self) -> str:
        """Get the fully qualified queue path."""
        return self.client.queue_path(self.project, self.location, self.queue)

    async def create_task(self, task_name: str, payload: Dict[str, Any],
                          timeout_seconds: Optional[int] = 1800
                          ) -> Dict[str, Any]:
        """
        Create a new task or retry an existing one.

        Args:
            task_name: Name/type of the task to create
            payload: Task payload containing job details and parameters

        Returns:
            Dict containing task creation status and details
        """
        # Get queue path
        parent = self._get_queue_path()

        # Set default retry configuration if not present
        if 'attempt_number' not in payload:
            payload['attempt_number'] = 1
        if 'max_retries' not in payload:
            payload['max_retries'] = 3

        dispatch_timeout_seconds = timeout_seconds or self.default_task_timeout

        # Validate timeout (max 30 minutes)
        dispatch_timeout_seconds = min(dispatch_timeout_seconds, 1800)

        # Convert to Duration format as expected by
        # https://cloud.google.com/tasks/docs/reference/rpc/google.cloud.tasks.v2#google.cloud.tasks.v2.Task.
        dispatch_timeout_duration: str = f"{dispatch_timeout_seconds}s"

        # Configure task with OIDC authentication
        task = {
            'http_request': {
                'http_method': tasks_v2.HttpMethod.POST,
                'url': f"{self.base_url}/api/v1/tasks/{task_name}",
                'headers': {'Content-Type': 'application/json'},
                'body': json.dumps(payload).encode(),
                'oidc_token': tasks_v2.OidcToken(
                    service_account_email=self.service_account_email,
                    audience=self.base_url
                ),
            },
            'dispatch_deadline': {'seconds': dispatch_timeout_duration}
        }

        # Create task and get response
        response = self.client.create_task(request={"parent": parent, "task": task})

        return {
            "status": "scheduled",
            "task_name": task_name,
            "task_id": response.name,
            "attempt_number": payload['attempt_number'],
            "max_retries": payload['max_retries'],
            "original_job_id": payload.get('original_job_id')
        }

    async def get_job_status(self, job_id: str) -> Dict[str, Any]:
        """
        Get detailed status information for a job.

        Args:
            job_id: ID of the job to query

        Returns:
            Dict containing job status and details

        Raises:
            KeyError: If job is not found
        """
        # Reuse BigQueryService implementation
        return await self.bq_service.get_job_status(job_id)

    async def list_failed_jobs(
            self,
            start_date: datetime,
            end_date: datetime,
            retryable_only: bool = False,
            limit: int = 100
    ) -> List[Dict[str, Any]]:
        """
        List failed jobs within a date range.

        Args:
            start_date: Start of date range to query
            end_date: End of date range to query
            retryable_only: If True, only return retryable jobs
            limit: Maximum number of jobs to return

        Returns:
            List of failed jobs with their details
        """
        # Reuse BigQueryService implementation
        return await self.bq_service.list_failed_jobs(
            start_date=start_date,
            end_date=end_date,
            retryable_only=retryable_only,
            limit=limit
        )
