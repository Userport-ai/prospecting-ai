# tenant_urls.py
import logging

from django.urls import path

from .tenant_viewset import TenantViewSet, TenantUserViewSet

logger = logging.getLogger(__name__)

logger.debug("[TENANT_URLS] Starting URL pattern definition...")

urlpatterns = [
    path('tenants/', TenantViewSet.as_view({
        'get': 'list',
        'post': 'create'
    }), name='tenant-list'),

    path('tenants/<uuid:pk>/', TenantViewSet.as_view({
        'get': 'retrieve',
        'put': 'update',
        'patch': 'partial_update',
        'delete': 'destroy'
    }), name='tenant-detail'),

    path('tenants/<uuid:pk>/invite-user/', TenantViewSet.as_view({
        'post': 'invite_user'
    }), name='tenant-invite-user'),

    path('tenants/<uuid:pk>/remove-user/', TenantViewSet.as_view({
        'post': 'remove_user'
    }), name='tenant-remove-user'),

    path('tenant-users/', TenantUserViewSet.as_view({
        'get': 'list'
    }), name='tenant-user-list'),

    path('tenant-users/<uuid:pk>/', TenantUserViewSet.as_view({
        'get': 'retrieve',
        'put': 'update',
        'patch': 'partial_update',
        'delete': 'destroy'
    }), name='tenant-user-detail'),

    path('tenant-users/<uuid:pk>/update-role/', TenantUserViewSet.as_view({
        'patch': 'update_role'
    }), name='tenant-user-update-role'),
]

logger.debug(f"[TENANT_URLS] Defined URL patterns: {urlpatterns}")