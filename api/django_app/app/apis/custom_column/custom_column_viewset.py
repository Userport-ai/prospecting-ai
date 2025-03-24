from django.db import transaction
from django.db.models import Count
from django.utils import timezone
from rest_framework import viewsets, status, serializers
from rest_framework.decorators import action
from rest_framework.response import Response

from app.models.custom_column import (
    CustomColumn, LeadCustomColumnValue, AccountCustomColumnValue
)
from app.models.serializers.custom_column_serializer import (
    CustomColumnSerializer, LeadCustomColumnValueSerializer, AccountCustomColumnValueSerializer
)
from app.apis.common import TenantScopedViewSet
from app.permissions import HasRole, UserRole
from app.services.worker_service import WorkerService
import uuid
import logging

logger = logging.getLogger(__name__)


class CustomColumnViewSet(TenantScopedViewSet):
    """ViewSet for managing CustomColumn."""

    queryset = CustomColumn.objects.all()
    serializer_class = CustomColumnSerializer
    permission_classes = [HasRole(allowed_roles=[
        UserRole.TENANT_ADMIN.value,
        UserRole.INTERNAL_ADMIN.value
    ])]
    filterset_fields = ['entity_type', 'product', 'is_active']
    ordering_fields = ['name', 'created_at', 'last_refresh']

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

        worker_service = WorkerService()

        try:
            # Initialize or update column settings for tracking
            settings = custom_column.settings or {}
            settings.update({
                'status': 'pending',
                'initiated_at': timezone.now().isoformat(),
                'initiated_by': str(request.user.id) if request.user else None,
                'total_entities': len(entity_ids)
            })

            # Create a unique request ID for idempotency
            request_id = str(uuid.uuid4())

            payload = {
                "column_id": str(custom_column.id),
                "entity_type": custom_column.entity_type,
                "entity_ids": entity_ids,
                "question": custom_column.question,
                "response_type": custom_column.response_type,
                "response_config": custom_column.response_config,
                "ai_config": custom_column.ai_config,
                "context_type": custom_column.context_type,
                "tenant_id": str(request.tenant.id),
                "product_id": str(custom_column.product_id),
                "request_id": request_id
            }

            # Update column's last_refresh and settings
            custom_column.last_refresh = timezone.now()
            custom_column.settings = settings
            custom_column.save(update_fields=['last_refresh', 'settings', 'updated_at'])

            # Prepare entities for processing
            if custom_column.entity_type == CustomColumn.EntityType.LEAD:
                self._prepare_lead_values(custom_column, entity_ids)
            else:
                self._prepare_account_values(custom_column, entity_ids)

            # Trigger the worker task
            response = worker_service.trigger_custom_column_generation(payload)

            return Response({
                "message": "Values generation initiated",
                "job_id": response.get("job_id"),
                "entity_count": len(entity_ids),
                "request_id": request_id
            })

        except Exception as e:
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
            # Get all lead IDs for this tenant and product
            entity_ids = list(
                self.get_queryset().get(id=custom_column.id).product.leads.values_list('id', flat=True)
            )
        else:
            # Get all account IDs for this tenant and product
            entity_ids = list(
                self.get_queryset().get(id=custom_column.id).product.accounts.values_list('id', flat=True)
            )

        if not entity_ids:
            return Response(
                {"message": "No entities found to refresh"},
                status=status.HTTP_200_OK
            )

        # Create a new request with these entity IDs
        request.data['entity_ids'] = [str(id) for id in entity_ids]
        return self.generate_values(request, pk)

    @action(detail=True, methods=['get'])
    def status(self, request, pk=None):
        """Get the current status of this custom column."""
        custom_column = self.get_object()

        # Get counts of values by status
        entity_model = LeadCustomColumnValue if custom_column.entity_type == CustomColumn.EntityType.LEAD else AccountCustomColumnValue
        status_counts = entity_model.objects.filter(column=custom_column).values('status').annotate(count=Count('status'))

        # Convert to a more readable format
        status_summary = {item['status']: item['count'] for item in status_counts}

        # Get the latest metadata
        metadata = custom_column.settings or {}
        current_status = metadata.get('status', 'unknown')

        # Calculate completion percentage
        completion_percentage = metadata.get('completion_percentage', 0)
        if current_status == 'completed':
            completion_percentage = 100

        # Return the status information
        return Response({
            "status": current_status,
            "last_refresh": custom_column.last_refresh,
            "completion_percentage": completion_percentage,
            "status_counts": status_summary,
            "metadata": metadata
        })

    def _prepare_lead_values(self, custom_column, lead_ids):
        """Create/update pending lead column values."""
        with transaction.atomic():
            for lead_id in lead_ids:
                LeadCustomColumnValue.objects.update_or_create(
                    column=custom_column,
                    lead_id=lead_id,
                    defaults={
                        'status': LeadCustomColumnValue.Status.PROCESSING,
                        'tenant': custom_column.tenant
                    }
                )

    def _prepare_account_values(self, custom_column, account_ids):
        """Create/update pending account column values."""
        with transaction.atomic():
            for account_id in account_ids:
                AccountCustomColumnValue.objects.update_or_create(
                    column=custom_column,
                    account_id=account_id,
                    defaults={
                        'status': AccountCustomColumnValue.Status.PROCESSING,
                        'tenant': custom_column.tenant
                    }
                )


class LeadCustomColumnValueViewSet(TenantScopedViewSet):
    """ViewSet for managing LeadCustomColumnValue."""

    queryset = LeadCustomColumnValue.objects.all()
    serializer_class = LeadCustomColumnValueSerializer
    permission_classes = [HasRole(allowed_roles=[
        UserRole.USER.value,
        UserRole.TENANT_ADMIN.value,
        UserRole.INTERNAL_ADMIN.value,
        UserRole.INTERNAL_CS.value
    ])]
    filterset_fields = ['column', 'lead', 'status']
    ordering_fields = ['generated_at']


class AccountCustomColumnValueViewSet(TenantScopedViewSet):
    """ViewSet for managing AccountCustomColumnValue."""

    queryset = AccountCustomColumnValue.objects.all()
    serializer_class = AccountCustomColumnValueSerializer
    permission_classes = [HasRole(allowed_roles=[
        UserRole.USER.value,
        UserRole.TENANT_ADMIN.value,
        UserRole.INTERNAL_ADMIN.value,
        UserRole.INTERNAL_CS.value
    ])]
    filterset_fields = ['column', 'account', 'status']
    ordering_fields = ['generated_at']