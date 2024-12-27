# app/permissions.py
import logging

from app.models import UserRole
from app.utils.permission_logging import PermissionLoggingMixin
from rest_framework import permissions

logger = logging.getLogger('permissions')


class BasePermission(PermissionLoggingMixin, permissions.BasePermission):
    """Base permission class with logging"""

    def check_role(self, request, required_role=None, allowed_roles=None):
        """
        Common method to check user roles with consistent error handling

        Args:
            request: The request object
            required_role: Single required role (optional)
            allowed_roles: List of allowed roles (optional)

        Returns:
            bool: Whether permission is granted
        """
        try:
            if not hasattr(request, 'user') or not request.user:
                logger.warning("No user found in request")
                return False

            if not hasattr(request.user, 'role'):
                logger.warning(f"No role attribute found for user {request.user.id}")
                return False

            user_role = request.user.role

            if required_role:
                result = user_role == required_role
                logger.debug(
                    f"Role check - User: {request.user.id}, Required: {required_role}, Actual: {user_role}, Result: {result}")
                return result

            if allowed_roles:
                result = user_role in allowed_roles
                logger.debug(
                    f"Role check - User: {request.user.id}, Allowed: {allowed_roles}, Actual: {user_role}, Result: {result}")
                return result

            logger.error("Neither required_role nor allowed_roles provided")
            return False

        except Exception as e:
            logger.error(f"Error checking role permission: {str(e)}", exc_info=True)
            return False


class IsTenantAdmin(BasePermission):
    """Permission check for tenant admin role"""

    def has_permission(self, request, view):
        return self.check_role(request, required_role=UserRole.TENANT_ADMIN.value)


class IsInternalAdmin(BasePermission):
    """Permission check for internal admin role"""

    def has_permission(self, request, view):
        return self.check_role(request, required_role=UserRole.INTERNAL_ADMIN.value)


class IsInternalCS(BasePermission):
    """Permission check for internal CS role"""

    def has_permission(self, request, view):
        return self.check_role(request, required_role=UserRole.INTERNAL_CS)


class HasRole(BasePermission):
    """Generic role-based permission check"""

    def __init__(self, allowed_roles):
        self.allowed_roles = allowed_roles
        super().__init__()

    def has_permission(self, request, view):
        return self.check_role(request, allowed_roles=self.allowed_roles)