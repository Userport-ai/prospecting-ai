import os
from typing import Dict, Any, Optional
from google.auth import default
from google.auth.transport.requests import Request
from google.oauth2 import id_token
from google.oauth2 import service_account
import httpx
import logging

logger = logging.getLogger(__name__)

class CallbackService:
    def __init__(self):
        """Initialize the callback service with OIDC auth"""
        self.django_base_url = os.environ.get('DJANGO_BASE_URL')
        if not self.django_base_url:
            raise ValueError("DJANGO_BASE_URL environment variable is required")

        self.callback_path = '/api/v2/internal/enrichment-callback/'
        self.audience = self.django_base_url.rstrip('/')

        try:
            # Check if running locally with service account file
            sa_file = os.getenv('GOOGLE_APPLICATION_CREDENTIALS', './secrets/service-account.json')
            if os.path.exists(sa_file):
                logger.debug("Using local service account file for authentication")
                self.credentials = service_account.IDTokenCredentials.from_service_account_file(
                    sa_file,
                    target_audience=self.audience
                )
                self._use_workload_identity = False
            else:
                # Use workload identity in cloud environment
                logger.debug("Using workload identity for authentication")
                self.credentials, self.project = default()
                self._use_workload_identity = True

            logger.debug(f"Credentials initialized. Type: {type(self.credentials)}")

        except Exception as e:
            logger.error(f"Failed to initialize credentials: {str(e)}")
            raise

    async def _get_id_token(self) -> str:
        """Get fresh ID token for Django callback authentication"""
        try:
            request = Request()

            if self._use_workload_identity:
                # For workload identity, fetch a new token directly
                return id_token.fetch_id_token(request, self.audience)
            else:
                # For service account credentials, use the built-in refresh mechanism
                if not self.credentials.valid:
                    self.credentials.refresh(request)
                return self.credentials.token

        except Exception as e:
            logger.error(f"Failed to get ID token: {str(e)}")
            raise

    async def send_callback(
            self,
            job_id: str,
            account_id: str,
            status: str,
            raw_data: Optional[Dict[str, Any]] = None,
            processed_data: Optional[Dict[str, Any]] = None,
            error_details: Optional[Dict[str, Any]] = None,
            source: str = 'jina_ai',
            is_partial: bool = False,
            completion_percentage: int = 100,
            attempt_number: Optional[int] = None,
            max_retries: Optional[int] = None
    ) -> bool:
        """
        Send callback to Django with enrichment results

        Args:
            job_id: Unique identifier for the job
            account_id: Account being enriched
            status: Current status (pending/processing/completed/failed)
            raw_data: Raw enrichment data (optional)
            processed_data: Processed enrichment data (optional)
            error_details: Error information if failed (optional)
            source: Data source identifier
            is_partial: Whether this is a partial completion
            completion_percentage: Percentage of job completed
            attempt_number: Current attempt number
            max_retries: Maximum retry attempts
        """
        try:
            # Get fresh OIDC token
            id_token = await self._get_id_token()

            # Prepare callback payload
            callback_data = {
                "job_id": job_id,
                "account_id": account_id,
                "status": status,
                "source": source,
                "is_partial": is_partial,
                "completion_percentage": completion_percentage
            }

            # Add optional data
            if raw_data is not None:
                callback_data["raw_data"] = raw_data
            if processed_data is not None:
                callback_data["processed_data"] = processed_data
            if error_details is not None:
                callback_data["error_details"] = error_details
            if attempt_number is not None:
                callback_data["attempt_number"] = attempt_number
            if max_retries is not None:
                callback_data["max_retries"] = max_retries

            # Make async request to Django
            async with httpx.AsyncClient() as client:
                response = await client.post(
                    f"{self.django_base_url}{self.callback_path}",
                    json=callback_data,
                    headers={
                        "Authorization": f"Bearer {id_token}",
                        "Content-Type": "application/json"
                    },
                    timeout=30.0
                )

            response.raise_for_status()
            logger.info(f"Callback successful for job {job_id}")
            return True

        except Exception as e:
            logger.error(f"Callback failed for job {job_id}: {str(e)}")
            # Don't raise the exception - let the task handle the failure
            return False