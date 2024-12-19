import os
import sys

from google.auth.exceptions import DefaultCredentialsError
from google.auth import default
from google.oauth2 import service_account
from firebase_admin import initialize_app, auth, credentials, get_app
from django.core.exceptions import ValidationError
from app.models import User


class FirebaseAuthService:
    def __init__(self):
        try:
            # First try to get existing app
            firebase_app = get_app()
        except ValueError:
            # App doesn't exist, initialize it
            try:
                # Check for local service account file first
                local_creds_path = os.getenv('FIREBASE_CREDS_PATH', '/secrets/service-account.json')
                if os.path.exists(local_creds_path):
                    # Use the local service account file if it exists
                    firebase_app = initialize_app(credentials.Certificate(local_creds_path))
                else:
                    # If local file doesn't exist, try to get default credentials (Workload Identity)
                    creds, project = default()
                    # Convert credentials to Certificate
                    cert_dict = {
                        "type": "service_account",
                        "project_id": project,
                        "private_key": creds.private_key,
                        "client_email": creds.service_account_email,
                        "token_uri": creds.token_uri,
                    }
                    firebase_app = initialize_app(credentials.Certificate(cert_dict))
            except (DefaultCredentialsError, AttributeError):
                raise

    @staticmethod
    def verify_and_get_user(id_token: str):
        """
        Verify Firebase token and return or create corresponding user
        """
        try:
            decoded_token = auth.verify_id_token(id_token)

            email = decoded_token.get('email')
            if not email:
                raise ValidationError("Email not found in Firebase token")

            user, created = User.objects.get_or_create(
                email=email,
                defaults={
                    'status': 'active',
                    'role': 'user'
                }
            )

            return user

        except auth.InvalidIdTokenError:
            raise ValidationError("Invalid Firebase token")
        except Exception as e:
            raise ValidationError(f"Authentication failed: {str(e)}")