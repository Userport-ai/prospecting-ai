from django_filters.rest_framework import DjangoFilterBackend
from rest_framework.decorators import action
from rest_framework.response import Response
from rest_framework import status
from django.db import transaction
from app.apis.common.base import TenantScopedViewSet
from app.models import UserRole, Account
from app.models.serializers.account_serializers import (
    AccountDetailsSerializer,
    AccountBulkCreateSerializer
)
from app.permissions import HasRole
from app.services.worker_service import WorkerService


class AccountsViewSet(TenantScopedViewSet):
    serializer_class = AccountDetailsSerializer
    queryset = Account.objects.all()
    filter_backends = [DjangoFilterBackend]
    filterset_fields =['id', 'website', 'linkedin_url', 'created_by']
    ordering_fields = ['name', 'created_at', 'updated_at']
    ordering = ['-created_at']  # Default sorting


    def get_permissions(self):
        return [HasRole(allowed_roles=[UserRole.USER, UserRole.TENANT_ADMIN,
                                       UserRole.INTERNAL_ADMIN, UserRole.INTERNAL_CS])]

    def _trigger_enrichment(self, accounts):
        """Helper method to trigger enrichment for accounts"""
        worker_service = WorkerService()

        accounts_list = accounts if isinstance(accounts, list) else [accounts]

        enrichment_data = [
            {"account_id": str(account.id), "company_name": account.name}
            for account in accounts_list
        ]

        try:
            return worker_service.trigger_account_enrichment(enrichment_data)
        except Exception as e:
            print(f"Failed to trigger enrichment: {str(e)}")
            return {"status": "failed", "error": str(e)}


    def create(self, request, *args, **kwargs):
        response = super().create(request, *args, **kwargs)

        if response.status_code == status.HTTP_201_CREATED:
            account = self.get_queryset().get(id=response.data['id'])
            enrichment_response = self._trigger_enrichment(account)
            response.data['enrichment_status'] = enrichment_response

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

        if len(accounts_data) > 1000:
            return Response(
                {"error": "Maximum 1000 accounts allowed per request"},
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

                enrichment_response = self._trigger_enrichment(created_accounts)

                response_data = {
                    "message": "Accounts created successfully",
                    "account_count": len(created_accounts),
                    "accounts": AccountDetailsSerializer(created_accounts, many=True).data,
                    "enrichment_status": enrichment_response,
                }

                return Response(response_data, status=status.HTTP_201_CREATED)

        except Exception as e:
            return Response(
                {"error": str(e)},
                status=status.HTTP_500_INTERNAL_SERVER_ERROR
            )
