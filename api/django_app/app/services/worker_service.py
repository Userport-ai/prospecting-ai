from typing import List, Dict, Any
import os
import requests
from django.conf import settings
from google.auth import default
from google.auth.transport.requests import Request
from google.oauth2 import id_token
from google.oauth2 import service_account
import google.auth.transport.requests
import urllib.parse
import logging

logger = logging.getLogger(__name__)

class WorkerService:
    def __init__(self):
        self.base_url = settings.WORKER_API_BASE_URL
        self.timeout = 30.0

        # Format the audience URL correctly for Cloud Run
        base_url = self.base_url.rstrip('/')
        parsed_url = urllib.parse.urlparse(base_url)
        self.audience = f"https://{parsed_url.netloc}"

        logger.debug(f"Initializing WorkerService with audience: {self.audience}")

        try:
            # Check if running locally with service account file
            sa_file = './service-account.json'
            if os.path.exists(sa_file):
                logger.debug("Using local service account file for authentication")
                self.credentials = service_account.IDTokenCredentials.from_service_account_file(
                    sa_file,
                    target_audience=self.audience
                )
            else:
                # Use workload identity in cloud environment
                logger.debug("Using workload identity for authentication")
                self.credentials, project = default()

                # Convert credentials to IDTokenCredentials if needed
                if not isinstance(self.credentials, service_account.IDTokenCredentials):
                    request = google.auth.transport.requests.Request()
                    self.credentials = service_account.IDTokenCredentials(
                        signer=self.credentials.signer,
                        service_account_email=self.credentials.service_account_email,
                        target_audience=self.audience
                    )

            logger.debug(f"Credentials initialized. Type: {type(self.credentials)}")

        except Exception as e:
            logger.error(f"Failed to initialize credentials: {str(e)}")
            raise

    def _get_id_token(self) -> str:
        """
        Gets a fresh ID token for Cloud Run authentication
        """
        try:
            request = google.auth.transport.requests.Request()

            # Refresh the token if needed
            if not self.credentials.valid:
                self.credentials.refresh(request)

            return self.credentials.token

        except Exception as e:
            logger.error(f"Failed to get ID token: {str(e)}")
            raise

    def trigger_account_enrichment(self, accounts: List[Dict[str, Any]]) -> Dict[str, Any]:
        """
        Triggers account enrichment with OIDC token authentication
        """
        try:
            # Get fresh ID token
            id_token = self._get_id_token()

            logger.debug(f"Making request to: {self.base_url}/api/v1/tasks/create/account_enhancement")

            # Make request with ID token in Authorization header
            response = requests.post(
                f"{self.base_url}/api/v1/tasks/create/account_enhancement",
                json={"accounts": accounts},
                headers={
                    "Authorization": f"Bearer {id_token}"
                },
                timeout=self.timeout
            )

            logger.debug(f"Response status: {response.status_code}")
            logger.debug(f"Response headers: {dict(response.headers)}")

            response.raise_for_status()
            return response.json()

        except Exception as e:
            logger.error(f"Failed to trigger account enrichment: {str(e)}")
            raise Exception(f"Failed to trigger account enrichment: {str(e)}")