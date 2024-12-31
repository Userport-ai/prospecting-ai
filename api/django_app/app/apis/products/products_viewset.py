from app.apis.common.base import TenantScopedViewSet
from app.models import Product, UserRole
from app.models.serializers import ProductDetailsSerializer
from app.permissions import IsTenantAdmin, HasRole
from rest_framework.permissions import IsAuthenticated


class ProductViewSet(TenantScopedViewSet):
    serializer_class = ProductDetailsSerializer
    queryset = Product.objects.all()

    def get_permissions(self):
        return [HasRole(allowed_roles=[UserRole.TENANT_ADMIN.value, UserRole.INTERNAL_ADMIN.value])]

    def get_queryset(self):
        """
        Example of extending the base queryset with additional filters
        """
        queryset = super().get_queryset()
        # Add any product-specific filters
        status = self.request.query_params.get('status')
        if status:
            queryset = queryset.filter(status=status)
        return queryset
