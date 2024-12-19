# app/permissions.py
from rest_framework import permissions
from app.models import UserRole


class IsTenantAdmin(permissions.BasePermission):
    """Permission check for tenant admin role"""

    def has_permission(self, request, view):
        return request.user.role == UserRole.TENANT_ADMIN


class IsInternalAdmin(permissions.BasePermission):
    """Permission check for internal admin role"""

    def has_permission(self, request, view):
        return request.user.role == UserRole.INTERNAL_ADMIN


class IsInternalCS(permissions.BasePermission):
    """Permission check for internal CS role"""

    def has_permission(self, request, view):
        return request.user.role == UserRole.INTERNAL_CS


class HasRole(permissions.BasePermission):
    """Generic role-based permission check"""

    def __init__(self, allowed_roles):
        self.allowed_roles = allowed_roles

    def has_permission(self, request, view):
        return request.user.role in self.allowed_roles
