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

from app.utils.retry_utils import with_retry
from app.utils.serialization_utils import serialize_custom_types

logger = logging.getLogger(__name__)

class WorkerService:
    def __init__(self):
        self.base_url = settings.WORKER_API_BASE_URL
        self.timeout = 120.0

        # Format the audience URL correctly for Cloud Run
        base_url = self.base_url.rstrip('/')
        parsed_url = urllib.parse.urlparse(base_url)
        if os.getenv('ENVIRONMENT') == 'local' and settings.DEBUG:
            # Force HTTP for local development
            self.audience = f"http://{parsed_url.netloc}"  # Use HTTP for local audience
        else:
            # Use HTTPS for non-local environments
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

    def _get_id_token(self) -> str:
        """
        Gets a fresh ID token for Cloud Run authentication
        """
        try:
            request = google.auth.transport.requests.Request()

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

    def trigger_lead_generation(self, payload: Dict[str, Any]) -> Dict[str, Any]:
        """
        Triggers lead generation with OIDC token authentication
        """
        try:
            if os.getenv('ENVIRONMENT') == 'local' and settings.DEBUG:
                headers = {
                    "Content-Type": "application/json"
                }
            else:
                id_token = self._get_id_token()
                headers = {
                    "Authorization": f"Bearer {id_token}",
                    "Content-Type": "application/json"
                }

            logger.debug(f"Making request to: {self.base_url}/api/v1/tasks/create/lead_identification_apollo")

            response = requests.post(
                f"{self.base_url}/api/v1/tasks/create/lead_identification_apollo",
                json=payload,
                headers=headers,
                timeout=self.timeout
            )

            logger.debug(f"Response status: {response.status_code}")
            logger.debug(f"Response headers: {dict(response.headers)}")

            response.raise_for_status()
            return response.json()

        except Exception as e:
            logger.error(f"Failed to trigger lead generation: {str(e)}")
            raise Exception(f"Failed to trigger lead generation: {str(e)}")

    def trigger_account_enrichment(self, accounts: List[Dict[str, Any]]) -> Dict[str, Any]:
        """
        Triggers account enrichment with OIDC token authentication
        """
        try:
            if os.getenv('ENVIRONMENT') == 'local' and settings.DEBUG:
                # Skip token auth in local development
                headers = {
                    "Content-Type": "application/json"
                }
            else:
                # Get fresh ID token
                id_token = self._get_id_token()
                headers = {
                    "Authorization": f"Bearer {id_token}",
                    "Content-Type": "application/json"
                }

            logger.debug(f"Making request to: {self.base_url}/api/v1/tasks/create/account_enhancement")

            # Make request with ID token in Authorization header
            response = requests.post(
                f"{self.base_url}/api/v1/tasks/create/account_enhancement",
                json={"accounts": accounts},
                headers=headers,
                timeout=self.timeout
            )

            logger.debug(f"Response status: {response.status_code}")
            logger.debug(f"Response headers: {dict(response.headers)}")

            response.raise_for_status()
            return response.json()

        except Exception as e:
            logger.error(f"Failed to trigger account enrichment: {str(e)}")
            raise Exception(f"Failed to trigger account enrichment: {str(e)}")

    def trigger_lead_enrichment(self, payload: Dict[str, Any]) -> Dict[str, Any]:
        """
        Triggers lead LinkedIn research enrichment with OIDC token authentication
        """
        try:
            if os.getenv('ENVIRONMENT') == 'local' and settings.DEBUG:
                headers = {
                    "Content-Type": "application/json"
                }
            else:
                token = self._get_id_token()
                headers = {
                    "Authorization": f"Bearer {token}",
                    "Content-Type": "application/json"
                }

            logger.debug(f"Making request to: {self.base_url}/api/v1/tasks/create/lead_linkedin_research")

            response = requests.post(
                f"{self.base_url}/api/v1/tasks/create/lead_linkedin_research",
                json=payload,
                headers=headers,
                timeout=self.timeout
            )

            logger.debug(f"Response status: {response.status_code}")
            logger.debug(f"Response headers: {dict(response.headers)}")

            response.raise_for_status()
            return response.json()

        except Exception as e:
            logger.error(f"Failed to trigger lead enrichment: {str(e)}")
            raise Exception(f"Failed to trigger lead enrichment: {str(e)}")

    def trigger_custom_column_generation(self, payload):
        """
        Triggers custom column value generation in the worker service.

        Args:
            payload (dict): A dictionary containing:
                - column_id: ID of the CustomColumn
                - entity_type: 'lead' or 'account'
                - entity_ids: List of entity IDs to process
                - question: The question to answer
                - response_type: The type of response expected
                - response_config: Configuration for the response
                - ai_config: Configuration for the AI model
                - context_type: Types of context to include
                - tenant_id: ID of the tenant
                - product_id: ID of the product
                - request_id: Unique ID for this request (for idempotency)

        Returns:
            dict: Response from worker service, including job_id
        """
        url = f"{self.base_url}/api/v1/tasks/create/custom_column"

        # Get an OIDC token for authentication
        id_token = self._get_id_token()

        headers = {
            "Authorization": f"Bearer {id_token}",
            "Content-Type": "application/json"
        }

        processed_payload = serialize_custom_types(payload)

        # Make request to worker service
        response = requests.post(
            url,
            json=processed_payload,
            headers=headers,
            timeout=self.timeout
        )

        # Check if the request was successful
        if response.status_code != 200:
            raise Exception(f"Failed to trigger custom column generation: {response.text}")

        return response.json()