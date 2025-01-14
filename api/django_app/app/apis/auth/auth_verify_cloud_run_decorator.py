# app/auth/cloud_run.py
import os
from functools import wraps
from typing import Callable
import google.auth.transport.requests
from django.conf import settings
from google.oauth2 import id_token
from rest_framework.exceptions import AuthenticationFailed
import logging

logger = logging.getLogger(__name__)

def verify_cloud_run_token(func: Callable) -> Callable:
    """Decorator to verify Cloud Run OIDC token"""

    @wraps(func)
    def wrapper(request, *args, **kwargs):
        if os.getenv('ENVIRONMENT') == 'local' and settings.DEBUG:
            return func(request, *args, **kwargs)

        logger.info("Received request headers: %s", request.headers)
        auth_header = request.headers.get('Authorization')
        logger.info("Auth header: %s", auth_header[:20] if auth_header else "None")
        if not auth_header:
            logger.error("No Authorization header in Cloud Run callback")
            raise AuthenticationFailed("Missing Authorization header")

        try:
            # Extract token
            auth_type, token = auth_header.split(' ')
            if auth_type.lower() != 'bearer':
                raise AuthenticationFailed("Invalid auth type")

            # Verify the token
            request_handler = google.auth.transport.requests.Request()

            # The audience should be your GKE service's external URL
            audience = os.getenv('USERPORT_BASE_URL', "https://app.userport.ai")

            id_info = id_token.verify_oauth2_token(
                token,
                request_handler,
                audience=audience
            )

            # Verify issuer
            expected_issuer = f"https://accounts.google.com"
            if id_info['iss'] not in [expected_issuer, "accounts.google.com"]:
                raise AuthenticationFailed("Invalid token issuer")

            # Verify service account
            expected_sa = os.getenv('WORKER_SERVICE_ACCOUNT_EMAIL')
            if id_info.get('email') != expected_sa:
                raise AuthenticationFailed("Invalid service account")

            # Add verified token info to request
            request.cloud_run_token_info = id_info

            return func(request, *args, **kwargs)

        except ValueError as e:
            logger.error(f"Token verification failed: {str(e)}")
            raise AuthenticationFailed("Invalid token")
        except Exception as e:
            logger.error(f"Callback authentication error: {str(e)}")
            raise AuthenticationFailed(str(e))

    return wrapper