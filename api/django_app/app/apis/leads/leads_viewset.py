from django_filters.rest_framework import DjangoFilterBackend
from rest_framework.decorators import action
from rest_framework.response import Response
from rest_framework import status
from django.db import transaction
from app.apis.common.base import TenantScopedViewSet
from app.models import UserRole, Lead
from app.models.serializers.lead_serializers import (
    LeadDetailsSerializer,
    LeadBulkCreateSerializer
)
from app.permissions import HasRole


class LeadsViewSet(TenantScopedViewSet):
    serializer_class = LeadDetailsSerializer
    queryset = Lead.objects.all()
    filter_backends = [DjangoFilterBackend]
    filterset_fields =['id', 'account', 'email', 'phone', 'created_by']
    ordering_fields = ['first_name', 'last_name', 'created_at', 'updated_at']
    ordering = ['-created_at']  # Default sorting

    def get_permissions(self):
        return [HasRole(allowed_roles=[UserRole.USER, UserRole.TENANT_ADMIN,
                                       UserRole.INTERNAL_ADMIN, UserRole.INTERNAL_CS])]


    @action(detail=False, methods=['post'])
    def bulk_create(self, request):
        """
        Bulk create leads with enrichment
        """
        # Get account_id and leads data
        account_id = request.data.get('account')
        if not account_id:
            return Response(
                {"error": "account_id is required"},
                status=status.HTTP_400_BAD_REQUEST
            )

        leads_data = request.data.get('leads', [])
        if not leads_data:
            return Response(
                {"error": "No leads provided"},
                status=status.HTTP_400_BAD_REQUEST
            )

        if len(leads_data) > 1000:
            return Response(
                {"error": "Maximum 1000 leads allowed per request"},
                status=status.HTTP_400_BAD_REQUEST
            )

        # Validate all leads
        serializer = LeadBulkCreateSerializer(data=leads_data, many=True)
        if not serializer.is_valid():
            return Response(serializer.errors, status=status.HTTP_400_BAD_REQUEST)

        # Bulk create leads
        try:
            with transaction.atomic():
                leads = []
                for lead_data in leads_data:
                    lead = Lead(
                        tenant=request.tenant,
                        account_id=account_id,
                        created_by=request.user,
                        **lead_data
                    )
                    leads.append(lead)

                created_leads = Lead.objects.bulk_create(leads)

                # Trigger enrichment for created leads
                lead_ids = [lead.id for lead in created_leads]
                # TODO: Trigger enrichment job

                response_data = {
                    "message": "Leads created successfully",
                    "lead_count": len(created_leads),
                    "leads": LeadDetailsSerializer(created_leads, many=True).data
                }

                return Response(response_data, status=status.HTTP_201_CREATED)

        except Exception as e:
            return Response(
                {"error": str(e)},
                status=status.HTTP_500_INTERNAL_SERVER_ERROR
            )