import logging
import warnings
from typing import List, Dict, Any
from django_filters.rest_framework import DjangoFilterBackend
from rest_framework.decorators import action
from rest_framework.filters import OrderingFilter
from rest_framework.response import Response
from rest_framework import status
from django.db import transaction
from app.apis.common.base import TenantScopedViewSet
from app.apis.leads.lead_generation_mixin import LeadGenerationMixin
from app.models import UserRole, Account, EnrichmentType
from app.models.serializers.account_serializers import (
    AccountDetailsSerializer,
    AccountBulkCreateSerializer
)
from app.permissions import HasRole
from app.services.worker_service import WorkerService

logger = logging.getLogger(__name__)

MAX_ACCOUNTS_PER_REQUEST = 2


class AccountsViewSet(TenantScopedViewSet, LeadGenerationMixin):
    serializer_class = AccountDetailsSerializer
    queryset = Account.objects.all()
    filter_backends = [DjangoFilterBackend, OrderingFilter]
    filterset_fields = ['id', 'website', 'linkedin_url', 'created_by']
    ordering_fields = ['name', 'created_at', 'updated_at']
    ordering = ['-created_at']

    def get_queryset(self):
        base_queryset = super().get_queryset()
        return base_queryset.select_related(
            'product',
            'created_by'
        ).prefetch_related('enrichment_statuses')

    def get_permissions(self):
        return [HasRole(allowed_roles=[UserRole.USER, UserRole.TENANT_ADMIN,
                                       UserRole.INTERNAL_ADMIN, UserRole.INTERNAL_CS])]

    def _trigger_enrichments_old(self, accounts):
        """[DEPRECATED] Helper method to trigger all enrichments for accounts"""
        warnings.warn("_trigger_enrichments_old is deprecated, use _trigger_enrichments instead")
        worker_service = WorkerService()
        accounts_list = accounts if isinstance(accounts, list) else [accounts]
        results = []

        for enrichment_type in [EnrichmentType.COMPANY_INFO, EnrichmentType.GENERATE_LEADS]:
            try:
                if enrichment_type == EnrichmentType.COMPANY_INFO:
                    enrichment_data = [
                        {"account_id": str(account.id), "website": account.website}
                        for account in accounts_list
                    ]
                    response = worker_service.trigger_account_enrichment(enrichment_data)

                elif enrichment_type == EnrichmentType.GENERATE_LEADS:
                    response = {
                        "account_responses": [
                            self._trigger_lead_generation(account)
                            for account in accounts_list
                        ]
                    }

                results.append({
                    "enrichment_type": enrichment_type,
                    "response": response
                })

            except Exception as e:
                logger.error(f"Failed to trigger {enrichment_type} enrichment: {str(e)}")
                results.append({
                    "enrichment_type": enrichment_type,
                    "status": "failed",
                    "error": str(e)
                })

        return results

    def _trigger_enrichments(self, accounts) -> List[Dict[str, Any]]:
        """Helper method to trigger all enrichments for accounts"""
        worker_service = WorkerService()
        accounts_list = accounts if isinstance(accounts, list) else [accounts]
        results = []

        for account in accounts_list:
            try:
                # Trigger Account Enrichment.
                account_response = worker_service.trigger_account_enrichment(accounts=[{"account_id": str(account.id), "website": account.website}])
                logger.debug(f"Triggered Account enrichment in worker for Account ID: {account.id}")

                # Trigger Lead Enrichment.
                lead_response = self._trigger_lead_generation(account)

                logger.debug(f"Triggered Leads generation in worker for Account ID: {account.id}")

                results.append({
                    "account_id": account.id,
                    "account_enrichment_response": account_response,
                    "lead_generation_response": lead_response
                })
            except Exception as e:
                logger.error(f"Failed to trigger enrichment for account ID: {account.id} with error: {e}")
                results.append({
                    "account_id": account.id,
                    "error": str(e)
                })

        return results

    def create(self, request, *args, **kwargs):
        response = super().create(request, *args, **kwargs)

        if response.status_code == status.HTTP_201_CREATED:
            account = self.get_queryset().get(id=response.data['id'])
            enrichment_responses = self._trigger_enrichments(account)
            response.data['enrichment_responses'] = enrichment_responses

            logger.info(f"Triggerd Account Enrichment successfully for Account: {account}.")

        return response

    @action(detail=False, methods=['post'])
    def bulk_create(self, request):
        """
        Bulk create accounts with enrichment
        """
        # Validate product_id
        product_id = request.data.get('product')
        if not product_id:
            return Response(
                {"error": "product_id is required"},
                status=status.HTTP_400_BAD_REQUEST
            )

        # Get accounts data
        accounts_data = request.data.get('accounts', [])
        if not accounts_data:
            return Response(
                {"error": "No accounts provided"},
                status=status.HTTP_400_BAD_REQUEST
            )

        if len(accounts_data) > MAX_ACCOUNTS_PER_REQUEST:
            return Response(
                {"error": f"Maximum {MAX_ACCOUNTS_PER_REQUEST} accounts allowed per request"},
                status=status.HTTP_400_BAD_REQUEST
            )

        # Validate all accounts
        serializer = AccountBulkCreateSerializer(data=accounts_data, many=True)
        if not serializer.is_valid():
            return Response(serializer.errors, status=status.HTTP_400_BAD_REQUEST)

        # Bulk create accounts
        try:
            with transaction.atomic():
                accounts = []
                for account_data in accounts_data:
                    account = Account(
                        tenant=request.tenant,
                        product_id=product_id,
                        created_by=request.user,
                        **account_data
                    )
                    accounts.append(account)

                created_accounts = Account.objects.bulk_create(accounts)
                created_accounts = list(Account.objects.filter(
                    id__in=[account.id for account in created_accounts]
                ).select_related('product'))  # Refresh to get related data

                enrichment_responses = self._trigger_enrichments(created_accounts)

                logger.info(f"Triggerd Bulk Account Enrichments successfully for Accounts: {accounts_data}.")
                response_data = {
                    "message": "Accounts created successfully",
                    "account_count": len(created_accounts),
                    "accounts": AccountDetailsSerializer(created_accounts, many=True).data,
                    "enrichment_responses": enrichment_responses,
                }

                return Response(response_data, status=status.HTTP_201_CREATED)

        except Exception as e:
            return Response(
                {"error": str(e)},
                status=status.HTTP_500_INTERNAL_SERVER_ERROR
            )
