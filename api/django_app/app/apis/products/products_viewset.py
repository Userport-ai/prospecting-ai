from django_filters.rest_framework import DjangoFilterBackend

from app.apis.common.base import TenantScopedViewSet
from app.models import Product, UserRole
from app.models.serializers import ProductDetailsSerializer
from app.permissions import IsTenantAdmin, HasRole
from rest_framework.permissions import IsAuthenticated


class ProductViewSet(TenantScopedViewSet):
    serializer_class = ProductDetailsSerializer
    queryset = Product.objects.all().order_by('-created_at')  # Apply ordering to the queryset directly
    filter_backends = [DjangoFilterBackend]
    filterset_fields = ['id', 'website', 'created_by']
    ordering = ['-created_at']  # Default sorting

    def get_permissions(self):
        return [HasRole(allowed_roles=[UserRole.TENANT_ADMIN.value, UserRole.INTERNAL_ADMIN.value])]
