import os
import logging
from firebase_admin import initialize_app, auth, credentials, get_app
from django.core.exceptions import ValidationError
from app.models import User

logger = logging.getLogger(__name__)

class FirebaseAuthService:
    def __init__(self):
        try:
            # First try to get existing app
            firebase_app = get_app()
            logger.debug("Using existing Firebase app")
        except ValueError:
            logger.debug("Initializing new Firebase app")
            try:
                # Check for local service account file first
                local_creds_path = os.getenv('FIREBASE_CREDS_PATH', '/secrets/service-account.json')
                if os.path.exists(local_creds_path):
                    logger.debug(f"Using credentials from: {local_creds_path}")
                    firebase_app = initialize_app(credentials.Certificate(local_creds_path))
                else:
                    logger.debug("Using Application Default Credentials")
                    cred = credentials.ApplicationDefault()
                    firebase_app = initialize_app(cred, {
                        'projectId': 'omega-winter-431704-u5'
                    })
            except Exception as e:
                logger.error(f"Firebase initialization error: {str(e)}")
                raise

    @staticmethod
    def verify_and_get_user(id_token: str):
        """
        Verify Firebase token and return or create corresponding user
        """
        try:
            logger.debug(f"Attempting to verify token: {id_token[:10]}...")
            decoded_token = auth.verify_id_token(id_token)
            logger.debug(f"Token decoded successfully: {decoded_token.keys()}")

            email = decoded_token.get('email')
            if not email:
                logger.error("No email found in token")
                raise ValidationError("Email not found in Firebase token")

            logger.debug(f"Found email: {email}")
            user, created = User.objects.get_or_create(
                email=email,
                defaults={
                    'status': 'active',
                    'role': 'user'
                }
            )
            logger.debug(f"User {'created' if created else 'found'}: {user.email}")

            return user

        except auth.InvalidIdTokenError as e:
            logger.error(f"Invalid token error: {str(e)}")
            raise ValidationError("Invalid Firebase token")
        except Exception as e:
            logger.error(f"Authentication error: {str(e)}")
            raise ValidationError(f"Authentication failed: {str(e)}")