import logging

from django.core import serializers

from app.apis.common.base import TenantScopedViewSet
from app.models import Tenant, User, UserRole
from app.models.serializers.tenant_serializers import (
    TenantCreateSerializer,
    TenantUserInviteSerializer,
    TenantSerializer,
    TenantUserSerializer
)
from app.models.users import UserStatus
from app.permissions import HasRole
from app.permissions import IsInternalAdmin
from django.db import transaction
from firebase_admin import auth as firebase_auth
from rest_framework import viewsets, status
from rest_framework.decorators import action
from rest_framework.response import Response

logger = logging.getLogger(__name__)


class TenantViewSet(viewsets.ModelViewSet):
    """
    ViewSet for managing tenants.
    - GET: Internal admins can see all tenants, tenant admins can see their own tenant
    - POST/PUT/DELETE: Only internal admins can modify tenants
    """
    logger.debug("TenantViewSet initialization")
    serializer_class = TenantSerializer
    queryset = Tenant.objects.all()
    permission_classes = [IsInternalAdmin]

    def get_queryset(self):
        queryset = super().get_queryset()
        # Filter queryset for tenant admins to only show their tenant
        if (
            self.request.user.role == UserRole.TENANT_ADMIN.value
            and hasattr(self.request.user, 'tenant')
        ):
            queryset = queryset.filter(id=self.request.user.tenant.id)
        return queryset

    def get_serializer_class(self):
        if self.action == 'create':
            logger.debug("Creating tenant...")
            return TenantCreateSerializer
        return self.serializer_class

    # For create/update/delete operations, ensure only internal admins have access
    def check_permissions(self, request):
        if request.method not in ['GET', 'HEAD', 'OPTIONS']:
            if not IsInternalAdmin().has_permission(request, self):
                self.permission_denied(request)
        return super().check_permissions(request)

class TenantUserViewSet(TenantScopedViewSet):
    """
    ViewSet for managing users within a tenant.
    """
    serializer_class = TenantUserSerializer
    permission_classes = [HasRole([UserRole.TENANT_ADMIN.value, UserRole.INTERNAL_ADMIN.value])]
    queryset = User.objects.all()

    def get_queryset(self):
        queryset = super().get_queryset()
        role = self.request.query_params.get('role')
        if role:
            queryset = queryset.filter(role=role)
        return queryset

    @action(detail=True, methods=['patch'], url_path='update-role')
    @transaction.atomic
    def update_role(self, request, pk=None):
        """
        Update a user's role within the tenant
        """
        user = self.get_object()
        new_role = request.data.get('role')

        if new_role not in UserRole.values:
            return Response(
                {"error": "Invalid role"},
                status=status.HTTP_400_BAD_REQUEST
            )

        user.role = new_role
        user.save()
        return Response(TenantUserSerializer(user).data)
