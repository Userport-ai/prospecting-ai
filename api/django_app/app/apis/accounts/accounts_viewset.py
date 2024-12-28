from app.apis.common.base import TenantScopedViewSet
from app.models import Product, UserRole, Account
from app.models.serializers.account_serializers import AccountDetailsSerializer
from app.permissions import HasRole


class AccountsViewSet(TenantScopedViewSet):
    serializer_class = AccountDetailsSerializer
    queryset = Account.objects.all()

    def get_permissions(self):
        return [HasRole(allowed_roles=[UserRole.USER, UserRole.TENANT_ADMIN,
                                       UserRole.INTERNAL_ADMIN, UserRole.INTERNAL_CS])]

    def get_queryset(self):
        queryset = super().get_queryset()
        status = self.request.query_params.get('status')
        if status:
            queryset = queryset.filter(status=status)
        return queryset
