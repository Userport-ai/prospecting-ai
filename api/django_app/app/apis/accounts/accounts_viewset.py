import logging
import warnings
from typing import List, Dict, Any

from django.db.models import Prefetch
from django_filters.rest_framework import DjangoFilterBackend
from rest_framework.decorators import action
from rest_framework.filters import OrderingFilter
from rest_framework.response import Response
from rest_framework import status
from rest_framework.pagination import PageNumberPagination
from django.db import transaction
from app.apis.common.base import TenantScopedViewSet
from app.apis.leads.lead_generation_mixin import LeadGenerationMixin
from app.models import UserRole, Account
from app.models.custom_column import AccountCustomColumnValue
from app.models.serializers.account_serializers import (
    AccountDetailsSerializer,
    AccountBulkCreateSerializer
)
from app.permissions import HasRole
from app.services.worker_service import WorkerService
from rest_framework.serializers import Serializer, BooleanField

logger = logging.getLogger(__name__)

MAX_ACCOUNTS_PER_REQUEST = 20


class EnrichmentSerializer(Serializer):
    """Serializer for enrichment flags"""
    account_enrichment = BooleanField(default=True)
    lead_enrichment = BooleanField(default=False)
    custom_columns = BooleanField(default=True)


class ClientControlledPagination(PageNumberPagination):
    page_size_query_param = 'page_size'
    max_page_size = 100


class AccountsViewSet(TenantScopedViewSet, LeadGenerationMixin):
    serializer_class = AccountDetailsSerializer
    queryset = Account.objects.all()
    filter_backends = [DjangoFilterBackend, OrderingFilter]
    # filterset_fields = ['id', 'website', 'linkedin_url', 'created_by']
    filterset_fields = {
        'id': ['exact', 'in'],  # Enable `id__in` filtering
        'website': ['exact'],
        'linkedin_url': ['exact'],
        'created_by': ['exact'],
    }
    ordering_fields = ['name', 'created_at', 'updated_at']
    ordering = ['-created_at']
    pagination_class = ClientControlledPagination

    def get_queryset(self):
        base_queryset = super().get_queryset()
        return base_queryset.select_related(
            'product',
            'created_by'
        ).prefetch_related(
            'enrichment_statuses',
            # Add prefetch for custom column values
            Prefetch(
                'custom_column_values',
                queryset=AccountCustomColumnValue.objects.filter(
                    column__deleted_at__isnull=True,
                ).select_related('column'),
                to_attr='prefetched_custom_column_values'
            )
        )

    def get_permissions(self):
        return [HasRole(allowed_roles=[UserRole.USER, UserRole.TENANT_ADMIN,
                                       UserRole.INTERNAL_ADMIN, UserRole.INTERNAL_CS])]

    def _trigger_enrichments(self, accounts, trigger_account_enrichment=True, trigger_lead_enrichment=False, trigger_custom_columns=True) -> List[Dict[str, Any]]:
        """
        Helper method to trigger selected enrichments for accounts
        
        Args:
            accounts: Single account or list of accounts to enrich
            trigger_account_enrichment: Whether to trigger account enrichment (default: True)
            trigger_lead_enrichment: Whether to trigger lead enrichment (default: False)
            trigger_custom_columns: Whether to trigger custom column generation (default: True)
            
        Returns:
            List of enrichment responses for each account
        """
        worker_service = WorkerService()
        accounts_list = accounts if isinstance(accounts, list) else [accounts]
        results = []

        for account in accounts_list:
            try:
                response_data = {
                    "account_id": account.id
                }
                
                if trigger_account_enrichment:
                    # Trigger Account Enrichment
                    account_response = worker_service.trigger_account_enrichment(
                        accounts=[{"account_id": str(account.id), "website": account.website}]
                    )
                    logger.debug(f"Triggered Account enrichment in worker for Account ID: {account.id}")
                    response_data["account_enrichment_response"] = account_response
                
                if trigger_lead_enrichment:
                    # Trigger Lead Enrichment
                    lead_response = self._trigger_lead_generation(account)
                    logger.debug(f"Triggered Leads generation in worker for Account ID: {account.id}")
                    response_data["lead_generation_response"] = lead_response
                
                if trigger_custom_columns:
                    # Trigger Custom Column Generation
                    try:
                        from app.utils.custom_column_utils import trigger_custom_column_generation
                        custom_column_response = trigger_custom_column_generation(
                            tenant_id=account.tenant_id,
                            entity_type='account',
                            entity_ids=[account.id],
                            respect_dependencies=True
                        )
                        logger.debug(f"Triggered Custom Column generation for Account ID: {account.id}")
                        response_data["custom_column_response"] = custom_column_response
                    except Exception as custom_column_error:
                        logger.error(f"Failed to trigger custom column generation for account ID: {account.id} with error: {custom_column_error}")
                        response_data["custom_column_error"] = str(custom_column_error)
                
                results.append(response_data)
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
            enrichment_responses = self._trigger_enrichments(
                account, 
                trigger_account_enrichment=True,
                trigger_lead_enrichment=False,
                trigger_custom_columns=False
            )
            response.data['enrichment_responses'] = enrichment_responses

            logger.info(f"Triggered Account Enrichment successfully for Account: {account}.")

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

            enrichment_responses = self._trigger_enrichments(
                created_accounts,
                trigger_account_enrichment=True,
                trigger_lead_enrichment=False,
                trigger_custom_columns=False
            )

            logger.info(f"Triggered Bulk Account Enrichments successfully for Accounts: {accounts_data}.")

            response_data = {
                "message": "Accounts created successfully",
                "account_count": len(created_accounts),
                "accounts": AccountDetailsSerializer(created_accounts, many=True).data,
                "enrichment_responses": enrichment_responses
            }

            return Response(response_data, status=status.HTTP_201_CREATED)

        except Exception as e:
            return Response(
                {"error": str(e)},
                status=status.HTTP_500_INTERNAL_SERVER_ERROR
            )
    
    @action(detail=False, methods=['post'])
    def bulk_trigger_enrichment(self, request):
        """
        Trigger specific enrichment types for multiple accounts
        
        Request body should include:
        {
            "account_ids": ["uuid1", "uuid2", ...],
            "account_enrichment": true,
            "lead_enrichment": true,
            "custom_columns": true
        }
        """
        account_ids = request.data.get('account_ids', [])
        if not account_ids:
            return Response(
                {"error": "No account_ids provided"},
                status=status.HTTP_400_BAD_REQUEST
            )
            
        # Validate the enrichment flags
        serializer = EnrichmentSerializer(data=request.data)
        if not serializer.is_valid():
            return Response(serializer.errors, status=status.HTTP_400_BAD_REQUEST)
        
        # Get the enrichment flags from the serializer
        trigger_account = serializer.validated_data.get('account_enrichment', True)
        trigger_lead = serializer.validated_data.get('lead_enrichment', False)
        trigger_custom = serializer.validated_data.get('custom_columns', False)

        if not (trigger_account or trigger_lead or trigger_custom):
            return {
                "message": "No enrichments to trigger",
                "account_count": 0,
                "enrichment_responses": []
            }

        # Get the accounts
        accounts = self.get_queryset().filter(id__in=account_ids)
        if not accounts:
            return Response(
                {"error": "No valid accounts found for the provided IDs"},
                status=status.HTTP_404_NOT_FOUND
            )
        
        # Trigger the selected enrichments
        try:
            enrichment_responses = self._trigger_enrichments(
                accounts,
                trigger_account_enrichment=trigger_account,
                trigger_lead_enrichment=trigger_lead,
                trigger_custom_columns=trigger_custom
            )
            
            response_data = {
                "message": "Enrichment triggered successfully",
                "account_count": len(accounts),
                "enrichment_responses": enrichment_responses
            }
            
            return Response(response_data, status=status.HTTP_200_OK)
        except Exception as e:
            logger.error(f"Failed to trigger enrichment for accounts with error: {e}")
            return Response(
                {"error": str(e)},
                status=status.HTTP_500_INTERNAL_SERVER_ERROR
            )
            
    @action(detail=True, methods=['post'])
    def trigger_enrichment(self, request, pk=None):
        """
        Trigger specific enrichment types for an account
        
        Request body should include flags for which enrichments to trigger:
        {
            "account_enrichment": true,
            "lead_enrichment": true,
            "custom_columns": true
        }
        """
        account = self.get_object()
        
        # Validate the enrichment flags
        serializer = EnrichmentSerializer(data=request.data)
        if not serializer.is_valid():
            return Response(serializer.errors, status=status.HTTP_400_BAD_REQUEST)
        
        # Get the enrichment flags from the serializer
        trigger_account = serializer.validated_data.get('account_enrichment', False)
        trigger_lead = serializer.validated_data.get('lead_enrichment', False)
        trigger_custom = serializer.validated_data.get('custom_columns', False)

        if not (trigger_account or trigger_lead or trigger_custom):
            return {
                "message": "No enrichments to trigger",
                "account_count": 0,
                "enrichment_responses": []
            }

        # Trigger the selected enrichments
        try:
            enrichment_responses = self._trigger_enrichments(
                account,
                trigger_account_enrichment=trigger_account,
                trigger_lead_enrichment=trigger_lead,
                trigger_custom_columns=trigger_custom
            )
            
            response_data = {
                "message": "Enrichment triggered successfully",
                "account_id": str(account.id),
                "enrichment_responses": enrichment_responses
            }
            
            return Response(response_data, status=status.HTTP_200_OK)
        except Exception as e:
            logger.error(f"Failed to trigger enrichment for account ID: {account.id} with error: {e}")
            return Response(
                {"error": str(e)},
                status=status.HTTP_500_INTERNAL_SERVER_ERROR
            )
