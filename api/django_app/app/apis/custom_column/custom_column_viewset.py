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
from app.services.worker_service import WorkerService

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

        worker_service = WorkerService()

        try:
            # Create a unique request ID for idempotency and job_id
            request_id = str(uuid.uuid4())
            job_id = str(uuid.uuid4())

            # Use atomic transaction for all database operations
            with transaction.atomic():
                # Update column's last_refresh and settings first
                custom_column.last_refresh = timezone.now()
                custom_column.save(update_fields=['last_refresh', 'updated_at'])

                # Prepare entities for processing - already contains transaction.atomic()
                if custom_column.entity_type == CustomColumn.EntityType.LEAD:
                    self._prepare_lead_values(custom_column, entity_ids)
                else:
                    self._prepare_account_values(custom_column, entity_ids)

            # Create column_config object that contains all column configuration
            column_config = {
                "id": str(custom_column.id),
                "name": custom_column.name,
                "description": custom_column.description or "",
                "question": custom_column.question,
                "response_type": custom_column.response_type,
                "response_config": custom_column.response_config,
                "examples": custom_column.response_config.get("examples", []),
                "validation_rules": custom_column.response_config.get("validation_rules", [])
            }

            # Get context data for entities - moved outside transaction for better performance
            # since it's a read-only operation
            context_data = self._get_entity_context_data(custom_column, entity_ids)

            # Create the payload according to what custom_column_generation_task expects
            payload = {
                "column_id": str(custom_column.id),
                "entity_ids": entity_ids,
                "column_config": column_config,
                "context_data": context_data,
                "tenant_id": str(request.tenant.id),
                "batch_size": 10,  # Default batch size
                "job_id": job_id,
                "concurrent_requests": 5,  # Default concurrency
                "request_id": request_id
            }

            # Trigger the worker task - moved outside transaction since it's an external call
            response = worker_service.trigger_custom_column_generation(payload)

            return Response({
                "message": "Values generation initiated",
                "job_id": response.get("job_id", job_id),
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
            entity_ids = list(
                Lead.objects.filter(tenant=request.tenant).values_list('id', flat=True)
            )
        else:
            # Get all account IDs for this tenant
            entity_ids = list(
                Account.objects.filter(tenant=request.tenant).values_list('id', flat=True)
            )

        if not entity_ids:
            return Response(
                {"message": "No entities found to refresh"},
                status=status.HTTP_200_OK
            )

        # Create a new request with these entity IDs
        request.data['entity_ids'] = [str(id) for id in entity_ids]
        return self.generate_values(request, pk)

    def _get_entity_context_data(self, custom_column, entity_ids):
        """Get comprehensive context data for entities.

        This function fetches all available data for the specified entities,
        regardless of the context_types in the custom column configuration.
        The AI model performs better with more context, so we include everything available.

        Returns:
            dict: Dictionary with entity_ids as keys and their context data as values.
        """
        context_data = {}
        entity_type = custom_column.entity_type

        try:
            # Create empty context for each entity to ensure they all have entries
            for entity_id in entity_ids:
                context_data[entity_id] = {}

            # For each entity, gather all available context data
            if entity_type == CustomColumn.EntityType.LEAD:
                # Fetch lead data with related account information
                leads = Lead.objects.filter(id__in=entity_ids).select_related('account', 'account__product')

                for lead in leads:
                    lead_context = {}

                    # Complete lead information
                    lead_context['lead_info'] = {
                        'id': str(lead.id),
                        'name': f"{lead.first_name} {lead.last_name}",
                        'first_name': lead.first_name,
                        'last_name': lead.last_name,
                        'role_title': lead.role_title,
                        'linkedin_url': lead.linkedin_url,
                        'email': lead.email,
                        'phone': lead.phone,
                        'enrichment_status': lead.enrichment_status,
                        'score': lead.score,
                        'last_enriched_at': lead.last_enriched_at.isoformat() if lead.last_enriched_at else None,
                        'source': lead.source,
                        'suggestion_status': lead.suggestion_status,
                        'custom_fields': lead.custom_fields or {},
                        'created_at': lead.created_at.isoformat() if lead.created_at else None
                    }

                    # Company context (if lead has an associated account)
                    if lead.account:
                        account = lead.account
                        lead_context['company'] = {
                            'id': str(account.id),
                            'name': account.name,
                            'website': account.website,
                            'location': account.location,
                            'employee_count': account.employee_count,
                            'customers': account.customers or [],
                            'competitors': account.competitors or [],
                            'technologies': account.technologies or {},
                            'custom_fields': account.custom_fields or {},
                            'recent_events': account.recent_events or []
                        }

                        # Add product info if available
                        if account.product:
                            product = account.product
                            lead_context['product'] = {
                                'id': str(product.id),
                                'name': product.name,
                                'description': product.description,
                                'icp_description': getattr(product, 'icp_description', None),
                                'persona_role_titles': getattr(product, 'persona_role_titles', {}),
                                'keywords': getattr(product, 'keywords', []),
                                'website': getattr(product, 'website', None)
                            }

                    # LinkedIn activity data and enrichment insights
                    if lead.enrichment_data:
                        # Extract LinkedIn activity if available
                        linkedin_activity = lead.enrichment_data.get('linkedin_activity', {})
                        if linkedin_activity:
                            lead_context['linkedin_activity'] = linkedin_activity

                        # Include personality insights if available
                        personality_insights = lead.enrichment_data.get('personality_insights', {})
                        if personality_insights:
                            lead_context['personality_insights'] = personality_insights

                        # Include any other enrichment data
                        for key, value in lead.enrichment_data.items():
                            if key not in ['linkedin_activity', 'personality_insights']:
                                lead_context[f'enrichment_{key}'] = value

                    context_data[str(lead.id)] = lead_context

            else:  # Account entity type
                # Fetch accounts with related product
                accounts = Account.objects.filter(id__in=entity_ids).select_related('product')

                for account in accounts:
                    account_context = {}

                    # Complete account information
                    account_context['account_info'] = {
                        'id': str(account.id),
                        'name': account.name,
                        'website': account.website,
                        'linkedin_url': account.linkedin_url,
                        'industry': account.industry,
                        'location': account.location,
                        'employee_count': account.employee_count,
                        'company_type': account.company_type,
                        'founded_year': account.founded_year,
                        'customers': account.customers or [],
                        'competitors': account.competitors or [],
                        'last_enriched_at': account.last_enriched_at.isoformat() if account.last_enriched_at else None,
                        'custom_fields': account.custom_fields or {},
                        'settings': account.settings or {},
                        'created_at': account.created_at.isoformat() if account.created_at else None
                    }

                    # Include all available detailed information
                    if account.technologies:
                        account_context['technologies'] = account.technologies

                    if account.funding_details:
                        account_context['funding_details'] = account.funding_details

                    if account.enrichment_sources:
                        account_context['enrichment_sources'] = account.enrichment_sources

                    if account.recent_events:
                        account_context['recent_events'] = account.recent_events

                    # Try to get enrichment summary if it has related data
                    try:
                        enrichment_summary = account.get_enrichment_summary()
                        if enrichment_summary:
                            account_context['enrichment_summary'] = {k: v for k, v in enrichment_summary.items()
                                                                     if (k != 'statuses' and k != 'last_update')}  # Exclude statuses objects
                    except:
                        pass  # Skip if error in getting enrichment summary

                    # Add product info if available
                    if account.product:
                        product = account.product
                        account_context['product'] = {
                            'id': str(product.id),
                            'name': product.name,
                            'description': product.description,
                            'icp_description': getattr(product, 'icp_description', None),
                            'persona_role_titles': getattr(product, 'persona_role_titles', {}),
                            'keywords': getattr(product, 'keywords', []),
                            'website': getattr(product, 'website', None),
                            'playbook_description': getattr(product, 'playbook_description', None)
                        }

                    # Get related leads count (to understand account size in the system)
                    try:
                        leads_count = Lead.objects.filter(account_id=account.id).count()
                        account_context['leads_count'] = leads_count
                    except:
                        pass

                    context_data[str(account.id)] = account_context

            return context_data

        except Exception as e:
            logger.error(f"Error getting context data: {str(e)}", exc_info=True)
            # Return an empty context for all entities to avoid failures
            return {entity_id: {} for entity_id in entity_ids}

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
    # Remove permission_classes and use get_permissions() instead
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
    # Remove permission_classes and use get_permissions() instead
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
