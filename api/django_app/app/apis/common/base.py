from django.core.exceptions import PermissionDenied
from django.db import transaction
from django.http import Http404
from rest_framework import viewsets, status
from rest_framework.permissions import IsAuthenticated
from rest_framework.response import Response


class TenantScopedViewSet(viewsets.ModelViewSet):
    """
    Base ViewSet that automatically scopes all queries to the current tenant
    and provides common functionality for all viewsets.
    """
    permission_classes = [IsAuthenticated]

    def get_queryset(self):
        """
        Filter queryset by tenant and handle soft deletes.
        Override this method in child classes if additional filtering is needed.
        """
        base_queryset = self.queryset if self.queryset is not None else self.get_serializer().Meta.model.objects
        return base_queryset.filter(tenant=self.request.user.tenant)

    def perform_create(self, serializer):
        """
        Automatically set tenant and created_by when creating objects
        """
        serializer.save(
            tenant=self.request.user.tenant,
            created_by=self.request.user
        )

    @transaction.atomic
    def perform_destroy(self, instance):
        """
        Implement soft delete by default
        """
        instance.delete(hard=False)

    def handle_exception(self, exc):
        """
        Custom exception handling for common cases
        """
        if isinstance(exc, PermissionDenied):
            return Response(
                {
                    "error": "FORBIDDEN",
                    "message": "You do not have permission to perform this action"
                },
                status=status.HTTP_403_FORBIDDEN
            )
        elif isinstance(exc, Http404):
            return Response(
                {
                    "error": "NOT_FOUND",
                    "message": "Requested resource not found"
                },
                status=status.HTTP_404_NOT_FOUND
            )

        return super().handle_exception(exc)