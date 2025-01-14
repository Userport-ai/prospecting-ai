import os
from typing import Dict, Any, Optional
from google.auth import default
from google.auth.transport.requests import Request
from google.oauth2 import id_token
from google.oauth2 import service_account
import httpx
import logging
import json

logger = logging.getLogger(__name__)

class CallbackService:
    def __init__(self):
        """Initialize the callback service with OIDC auth"""
        logger.info("Initializing CallbackService")

        self.django_base_url = os.environ.get('DJANGO_BASE_URL')
        if not self.django_base_url:
            logger.error("DJANGO_BASE_URL environment variable is missing")
            raise ValueError("DJANGO_BASE_URL environment variable is required")

        logger.info(f"Using Django base URL: {self.django_base_url}")
        self.callback_path = '/api/v2/internal/enrichment-callback/'
        self.audience = self.django_base_url.rstrip('/')

        try:
            # Check if running locally with service account file
            sa_file = os.getenv('GOOGLE_APPLICATION_CREDENTIALS', './secrets/service-account.json')
            if os.path.exists(sa_file):
                logger.info(f"Using local service account file for authentication: {sa_file}")
                self.credentials = service_account.IDTokenCredentials.from_service_account_file(
                    sa_file,
                    target_audience=self.audience
                )
                self._use_workload_identity = False
                logger.info("Successfully initialized service account credentials")
            else:
                # Use workload identity in cloud environment
                logger.info("Attempting to use workload identity for authentication")
                self.credentials, self.project = default()
                self._use_workload_identity = True
                logger.info(f"Successfully initialized workload identity credentials for project: {self.project}")

            logger.debug(f"Credentials initialized. Type: {type(self.credentials)}, Workload Identity: {self._use_workload_identity}")

        except Exception as e:
            logger.error(f"Failed to initialize credentials: {str(e)}", exc_info=True)
            raise

    async def _get_id_token(self) -> str:
        """Get fresh ID token for Django callback authentication"""
        logger.debug("Attempting to get fresh ID token")
        try:
            request = Request()

            if self._use_workload_identity:
                logger.debug("Fetching ID token using workload identity")
                token = id_token.fetch_id_token(request, self.audience)
                logger.debug("Successfully obtained workload identity token")
                return token
            else:
                logger.debug("Checking service account credentials validity")
                if not self.credentials.valid:
                    logger.info("Refreshing expired service account credentials")
                    self.credentials.refresh(request)
                logger.debug("Successfully obtained service account token")
                return self.credentials.token

        except Exception as e:
            logger.error(f"Failed to get ID token: {str(e)}", exc_info=True)
            raise

    async def send_callback(
            self,
            job_id: str,
            account_id: str,
            status: str,
            enrichment_type: str = 'company_info',
            raw_data: Optional[Dict[str, Any]] = None,
            processed_data: Optional[Dict[str, Any]] = None,
            error_details: Optional[Dict[str, Any]] = None,
            source: str = 'jina_ai',
            is_partial: bool = False,
            completion_percentage: int = 100,
            attempt_number: Optional[int] = None,
            max_retries: Optional[int] = None
    ) -> bool:
        """Send callback to Django with enrichment results"""
        logger.info(f"Sending callback for job_id: {job_id}, account_id: {account_id}, status: {status}, processed_data: {processed_data}, error_details: {error_details}")

        try:
            # Get fresh OIDC token
            logger.debug(f"Requesting fresh ID token for job {job_id}")
            id_token = await self._get_id_token()
            logger.debug(f"Successfully obtained ID token for job {job_id}. Got token: {id_token[:10]}...")

            # Prepare callback payload
            callback_data = {
                "job_id": job_id,
                "account_id": account_id,
                "status": status,
                "enrichment_type": enrichment_type,  # Add this field
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

            logger.debug(f"Prepared callback data for job {job_id}: {json.dumps({k: '...' if k in ['raw_data', 'processed_data', 'error_details'] else v for k, v in callback_data.items()})}")

            # Make async request to Django
            callback_url = f"{self.django_base_url}{self.callback_path}"
            logger.info(f"Sending callback to {callback_url} for job {job_id}")

            async with httpx.AsyncClient() as client:
                logger.debug(f"Making POST request for job {job_id}")
                response = await client.post(
                    callback_url,
                    json=callback_data,
                    headers={
                        "Authorization": f"Bearer {id_token}",
                        "Content-Type": "application/json"
                    },
                    timeout=30.0
                )

                logger.debug(f"Received response for job {job_id}: Status {response.status_code}")
                response.raise_for_status()
                logger.info(f"Callback successful for job {job_id} with status code {response.status_code}")
                return True

        except httpx.TimeoutException as e:
            logger.error(f"Callback timeout for job {job_id}: {str(e)}", exc_info=True)
            return False
        except httpx.HTTPStatusError as e:
            logger.error(f"Callback HTTP error for job {job_id}: Status {e.response.status_code}, Response: {e.response.text}", exc_info=True)
            return False
        except Exception as e:
            logger.error(f"Callback failed for job {job_id}: {str(e)}", exc_info=True)
            return False