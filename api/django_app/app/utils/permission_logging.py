# app/utils/permission_logging.py
import functools
import logging
import traceback
from typing import Any, Callable

from rest_framework.request import Request
from rest_framework.views import APIView

logger = logging.getLogger('permissions')


def log_permission_check(func: Callable) -> Callable:
    """
    Decorator to log permission checks with detailed information
    """

    @functools.wraps(func)
    def wrapper(*args, **kwargs) -> bool:
        # The first arg will be the permission class instance
        permission_class = args[0]
        # The second arg will be the request
        request = args[1]
        class_name = permission_class.__class__.__name__

        # Get endpoint information
        endpoint = f"{request.method} {request.path}"
        user_id = getattr(request.user, 'id', 'Anonymous')
        user_role = getattr(request.user, 'role', 'Unknown')
        tenant_id = getattr(request, 'tenant_id', None)

        # Log the permission check attempt
        logger.debug(
            f"Permission check started | "
            f"Class: {class_name} | "
            f"Endpoint: {endpoint} | "
            f"User ID: {user_id} | "
            f"Role: {user_role} | "
            f"Tenant: {tenant_id}"
        )

        try:
            result = func(*args, **kwargs)

            # Log the result
            log_level = logging.INFO if result else logging.WARNING
            logger.log(
                log_level,
                f"Permission check completed | "
                f"Class: {class_name} | "
                f"Endpoint: {endpoint} | "
                f"Result: {'Granted' if result else 'Denied'} | "
                f"User ID: {user_id} | "
                f"Role: {user_role} | "
                f"Tenant: {tenant_id}"
            )

            return result

        except Exception as e:
            # Log any exceptions during permission check
            logger.error(
                f"Permission check failed | "
                f"Class: {class_name} | "
                f"Endpoint: {endpoint} | "
                f"Error: {str(e)} | "
                f"User ID: {user_id} | "
                f"Role: {user_role} | "
                f"Tenant: {tenant_id}\n"
                f"Traceback: {traceback.format_exc()}"
            )
            return False

    return wrapper


class PermissionLoggingMixin:
    """
    Mixin to add logging to permission classes
    """

    @log_permission_check
    def has_permission(self, request, view):
        return super().has_permission(request, view)

    @log_permission_check
    def has_object_permission(self, request, view, obj):
        return super().has_object_permission(request, view, obj)