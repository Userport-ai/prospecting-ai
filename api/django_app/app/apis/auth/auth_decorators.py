from functools import wraps
from rest_framework.exceptions import ValidationError, PermissionDenied
from app.services import FirebaseAuthService
import logging

logger = logging.getLogger(__name__)


def login_required(view_func):
    """Decorator to verify Firebase authentication token"""

    @wraps(view_func)
    def wrapped_view(request, *args, **kwargs):
        auth_header = request.headers.get('Authorization')

        if not auth_header:
            logger.error("No Authorization header found")
            raise ValidationError({"error": "UNAUTHORIZED", "message": "Authorization header is required"})

        try:
            auth_type, token = auth_header.split(' ')
            logger.debug(f"Auth type: {auth_type}")

            if auth_type.lower() != 'bearer':
                logger.error(f"Invalid auth type: {auth_type}")
                raise ValidationError({"error": "INVALID_AUTH_TYPE", "message": "Invalid authorization type"})
        except ValueError:
            logger.error("Could not split auth header into type and token")
            raise ValidationError({"error": "INVALID_AUTH_HEADER", "message": "Invalid authorization header format"})

        try:
            firebase_auth = FirebaseAuthService()
            logger.debug("Firebase auth service initialized")

            user = firebase_auth.verify_and_get_user(token)
            logger.debug(f"User authenticated: {user.email}")

            request.user = user
        except Exception as e:
            logger.error(f"Firebase authentication failed: {str(e)}")
            raise ValidationError({"error": "AUTH_FAILED", "message": str(e)})

        return view_func(request, *args, **kwargs)

    return wrapped_view