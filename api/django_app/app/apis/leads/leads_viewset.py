from django.db import transaction
from django_filters.rest_framework import DjangoFilterBackend
from rest_framework import status
from rest_framework.decorators import action
from rest_framework.filters import OrderingFilter
from rest_framework.response import Response

from app.apis.common.base import TenantScopedViewSet
from app.apis.common.lead_generation_mixin import LeadGenerationMixin
from app.models import UserRole, Lead, Account
from app.models.serializers.lead_serializers import (
    LeadDetailsSerializer,
    LeadBulkCreateSerializer
)
from app.permissions import HasRole
from app.services.worker_service import WorkerService


class LeadsViewSet(TenantScopedViewSet, LeadGenerationMixin):
    serializer_class = LeadDetailsSerializer
    queryset = Lead.objects.all()
    filter_backends = [DjangoFilterBackend, OrderingFilter]
    filterset_fields =['id', 'account', 'email', 'phone', 'created_by', 'suggestion_status']
    ordering_fields = ['first_name', 'last_name', 'created_at', 'updated_at']
    ordering = ['-created_at']  # Default sorting

    def get_permissions(self):
        return [HasRole(allowed_roles=[UserRole.USER, UserRole.TENANT_ADMIN,
                                       UserRole.INTERNAL_ADMIN, UserRole.INTERNAL_CS])]

    @action(detail=False, methods=['post'])
    def generate(self, request):
        """
        Trigger lead generation for an account
        """
        account_id = request.data.get('account')
        if not account_id:
            return Response(
                {"error": "account_id is required"},
                status=status.HTTP_400_BAD_REQUEST
            )

        try:
            account = Account.objects.select_related('product').get(
                id=account_id,
                tenant=request.tenant
            )

            if not account.linkedin_url:
                return Response(
                    {"error": "Account must have a LinkedIn URL for lead generation"},
                    status=status.HTTP_400_BAD_REQUEST
                )

            response = self._trigger_lead_generation(account)

            return Response({
                "message": "Lead generation started",
                "job_id": response.get('job_id'),
                "account_id": str(account.id)
            })

        except Account.DoesNotExist:
            return Response(
                {"error": "Account not found"},
                status=status.HTTP_404_NOT_FOUND
            )
        except Exception as e:
            return Response(
                {"error": str(e)},
                status=status.HTTP_500_INTERNAL_SERVER_ERROR
            )

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