import logging
import uuid

from django.db import transaction
from django.utils import timezone
from rest_framework import status
from rest_framework.decorators import action
from rest_framework.response import Response

from app.apis.common import TenantScopedViewSet
from app.models import Lead, Account
from app.models.custom_column import (
    CustomColumn, LeadCustomColumnValue, AccountCustomColumnValue
)
from app.models.serializers.custom_column_serializer import (
    CustomColumnSerializer, LeadCustomColumnValueSerializer, AccountCustomColumnValueSerializer
)
from app.permissions import HasRole, UserRole
from app.utils.custom_column_utils import (
    get_entity_context_data, get_column_config, trigger_custom_column_generation
)

logger = logging.getLogger(__name__)


class CustomColumnViewSet(TenantScopedViewSet):
    """ViewSet for managing CustomColumn."""

    queryset = CustomColumn.objects.all()
    serializer_class = CustomColumnSerializer
    filterset_fields = ['entity_type', 'is_active']
    ordering_fields = ['name', 'created_at', 'last_refresh']

    def get_permissions(self):
        """Return the permissions that this view requires."""
        return [HasRole(allowed_roles=[
            UserRole.TENANT_ADMIN.value,
            UserRole.INTERNAL_ADMIN.value
        ])]

    def perform_create(self, serializer):
        """Create a new custom column."""
        super().perform_create(serializer)

    @action(detail=True, methods=['post'])
    def generate_values(self, request, pk=None):
        """Trigger generation of values for this custom column."""
        custom_column = self.get_object()

        # Get entity IDs to process
        entity_ids = request.data.get('entity_ids', [])
        if not entity_ids:
            return Response(
                {"error": "No entity IDs provided"},
                status=status.HTTP_400_BAD_REQUEST
            )

        try:
            # Create a unique request ID for idempotency and job_id
            request_id = str(uuid.uuid4())
            job_id = str(uuid.uuid4())

            # Use atomic transaction for all database operations
            with transaction.atomic():
                # Update column's last_refresh
                custom_column.last_refresh = timezone.now()
                custom_column.save(update_fields=['last_refresh', 'updated_at'])

            # Use the utility function to trigger generation
            results = trigger_custom_column_generation(
                tenant_id=str(request.tenant.id),
                column_id=str(custom_column.id),
                entity_ids=entity_ids,
                request_id=request_id,
                job_id=job_id
            )

            if not results:
                return Response(
                    {"error": "Failed to trigger generation"},
                    status=status.HTTP_500_INTERNAL_SERVER_ERROR
                )

            result = results[0]  # We only have one result since we specified column_id

            return Response({
                "message": "Values generation initiated",
                "job_id": result.get("job_id", job_id),
                "entity_count": len(entity_ids),
                "request_id": request_id
            })

        except Exception as e:
            # Log the error with traceback
            logger.error(f"Error triggering custom column generation: {str(e)}", exc_info=True)
            return Response(
                {"error": f"Failed to trigger generation: {str(e)}"},
                status=status.HTTP_500_INTERNAL_SERVER_ERROR
            )

    @action(detail=True, methods=['post'], url_path='force-refresh')
    def force_refresh(self, request, pk=None):
        """Force refresh all values for this custom column."""
        custom_column = self.get_object()

        # Get entity IDs based on entity_type
        entity_ids = []
        if custom_column.entity_type == CustomColumn.EntityType.LEAD:
            # Get all lead IDs for this tenant
            entity_ids = list(str(id) for id in
                              Lead.objects.filter(tenant=request.tenant).values_list('id', flat=True)
                              )
        else:
            # Get all account IDs for this tenant
            entity_ids = list(str(id) for id in
                              Account.objects.filter(tenant=request.tenant).values_list('id', flat=True)
                              )

        if not entity_ids:
            return Response(
                {"message": "No entities found to refresh"},
                status=status.HTTP_200_OK
            )

        # Create a new request with these entity IDs
        request.data['entity_ids'] = entity_ids
        return self.generate_values(request, pk)


class LeadCustomColumnValueViewSet(TenantScopedViewSet):
    """ViewSet for managing LeadCustomColumnValue."""

    queryset = LeadCustomColumnValue.objects.all()
    serializer_class = LeadCustomColumnValueSerializer
    filterset_fields = ['column', 'lead', 'status']
    ordering_fields = ['generated_at']

    def get_permissions(self):
        """Return the permissions that this view requires."""
        return [HasRole(allowed_roles=[
            UserRole.USER.value,
            UserRole.TENANT_ADMIN.value,
            UserRole.INTERNAL_ADMIN.value,
            UserRole.INTERNAL_CS.value
        ])]


class AccountCustomColumnValueViewSet(TenantScopedViewSet):
    """ViewSet for managing AccountCustomColumnValue."""

    queryset = AccountCustomColumnValue.objects.all()
    serializer_class = AccountCustomColumnValueSerializer
    filterset_fields = ['column', 'account', 'status']
    ordering_fields = ['generated_at']

    def get_permissions(self):
        """Return the permissions that this view requires."""
        return [HasRole(allowed_roles=[
            UserRole.USER.value,
            UserRole.TENANT_ADMIN.value,
            UserRole.INTERNAL_ADMIN.value,
            UserRole.INTERNAL_CS.value
        ])]