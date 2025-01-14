from django.conf import settings
from rest_framework import authentication
from rest_framework import exceptions
from app.services import FirebaseAuthService
import logging

logger = logging.getLogger(__name__)
class FirebaseAuthMiddleware(authentication.BaseAuthentication):
    """
    Middleware to authenticate requests using Firebase tokens and match with Django users
    """

    def authenticate(self, request):
        logger.info(f"FirebaseAuthMiddleware: Processing request for path {request.path}")
        logger.info(f"Exempt paths: {getattr(settings, 'FIREBASE_AUTH_EXEMPT_PATHS', [])}")

        # Skip authentication for paths that don't need it
        if getattr(request, '_skip_firebase_auth', False):
            return None

        # Check if path is in exempt list
        if hasattr(settings, 'FIREBASE_AUTH_EXEMPT_PATHS') and request.path in settings.FIREBASE_AUTH_EXEMPT_PATHS:
            logger.info(f"Path {request.path} is exempt from Firebase auth")
            return None

        # Get the auth header
        auth_header = request.META.get('HTTP_AUTHORIZATION')
        if not auth_header:
            return None

        # Extract the token
        try:
            auth_type, token = auth_header.split(' ')
            if auth_type.lower() != 'bearer':
                return None
        except ValueError:
            return None

        if not token:
            return None

        # Verify token and get/create user
        try:
            firebase_auth = FirebaseAuthService()
            user = firebase_auth.verify_and_get_user(token)

            user.update_last_login()

            return (user, None)
        except exceptions.AuthenticationFailed as e:
            raise e
        except Exception as e:
            raise exceptions.AuthenticationFailed(str(e))

    def authenticate_header(self, request):
        return 'Bearer'