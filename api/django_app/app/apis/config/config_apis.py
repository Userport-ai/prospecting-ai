# apis/config_apis.py
from django.db import transaction, models
from rest_framework import serializers, viewsets
from rest_framework.decorators import action, api_view, permission_classes
from rest_framework.exceptions import PermissionDenied
from rest_framework.permissions import IsAuthenticated
from rest_framework.response import Response

from app.apis.common.base import TenantScopedViewSet
from app.models import Config, ConfigScope
from app.models import Settings, UserRole
from app.permissions import IsInternalAdmin
from app.models.serializers import SettingsSerializer


class ConfigSerializer(serializers.ModelSerializer):
    class Meta:
        model = Config
        fields = ['id', 'key', 'value', 'scope', 'description', 'tenant', 'user']
        read_only_fields = ['created_at', 'updated_at']

class ConfigViewSet(viewsets.ModelViewSet):
    serializer_class = ConfigSerializer
    queryset = Config.objects.all()
    permission_classes = [IsInternalAdmin]


class SettingsViewSet(TenantScopedViewSet):
    serializer_class = SettingsSerializer
    queryset = Settings.objects.all()

    def get_queryset(self):
        queryset = super().get_queryset()
        user = self.request.user

        if user.role == UserRole.INTERNAL_ADMIN:
            return queryset

        if user.role == UserRole.TENANT_ADMIN:
            # Tenant admins can see all settings within their tenant
            return queryset

        # Regular users can only see their own settings and tenant settings
        return queryset.filter(
            models.Q(user=user) | models.Q(user__isnull=True)
        )

    def perform_create(self, serializer):
        user = self.request.user
        data = serializer.validated_data
        target_user = data.get('user')

        if user.role == UserRole.INTERNAL_ADMIN:
            # Internal admin can do anything
            pass
        elif user.role == UserRole.TENANT_ADMIN:
            # Tenant admin can only create tenant-level settings
            if target_user is not None:
                raise PermissionDenied("Tenant admins can only create tenant-level settings")
        else:
            # Regular users can only create their own settings
            if target_user and target_user != user:
                raise PermissionDenied("Users can only create their own settings")
            data['user'] = user

        super().perform_create(serializer)

def perform_update(self, serializer):
    user = self.request.user
    instance = serializer.instance
    target_user = serializer.validated_data.get('user', instance.user)

    if user.role == UserRole.INTERNAL_ADMIN:
        # Internal admin can do anything
        pass
    elif user.role == UserRole.TENANT_ADMIN:
        # Tenant admin can ONLY modify tenant-level settings
        if instance.user is not None or target_user is not None:
            raise PermissionDenied("Tenant admins can only modify tenant-level settings")
    else:
        # Regular users can only modify their own settings
        if instance.user != user:
            raise PermissionDenied("Users can only modify their own settings")

    serializer.save()

def perform_destroy(self, instance):
    user = self.request.user

    if user.role == UserRole.INTERNAL_ADMIN:
        # Internal admin can do anything
        pass
    elif user.role == UserRole.TENANT_ADMIN:
        # Tenant admin can ONLY delete tenant-level settings
        if instance.user is not None:
            raise PermissionDenied("Tenant admins can only delete tenant-level settings")
    else:
        # Regular users can only delete their own settings
        if instance.user != user:
            raise PermissionDenied("Users can only delete their own settings")

    super().perform_destroy(instance)

    @action(detail=False, methods=['post'])
    def bulk_update(self, request):
        """
        Bulk update settings
        """
        user = request.user
        settings_data = request.data.get('settings', [])

        with transaction.atomic():
            updated_settings = []
            for item in settings_data:
                if user.role == UserRole.INTERNAL_ADMIN:
                    # Internal admin can update any settings
                    target_user = item.get('user')
                elif user.role == UserRole.TENANT_ADMIN:
                    # Tenant admin can only update tenant settings
                    target_user = None
                else:
                    # Regular users can only update their own settings
                    target_user = user

                setting, created = Settings.objects.update_or_create(
                    tenant=request.user.tenant,
                    user=target_user,
                    key=item['key'],
                    defaults={'value': item['value']}
                )
                updated_settings.append(setting)

            serializer = self.get_serializer(updated_settings, many=True)
            return Response(serializer.data)


@api_view(['GET'])
@permission_classes([IsAuthenticated])
def get_merged_context(request):
    """
    Get merged configuration and settings with tenant info
    GET /api/v2/context/
    Returns merged configuration where user settings override tenant settings,
    and tenant configs override global configs
    """
    user = request.user
    tenant = request.user.tenant

    # Collect all configs
    merged_config = {}

    # Start with global configs (lowest priority)
    global_configs = Config.objects.filter(
        scope=ConfigScope.GLOBAL
    ).values('key', 'value')

    for config in global_configs:
        merged_config[config['key']] = config['value']

    # Override with tenant configs
    tenant_configs = Config.objects.filter(
        scope=ConfigScope.TENANT,
        tenant=tenant
    ).values('key', 'value')

    for config in tenant_configs:
        merged_config[config['key']] = config['value']

    # Override with user configs
    user_configs = Config.objects.filter(
        scope=ConfigScope.USER,
        tenant=tenant,
        user=user
    ).values('key', 'value')

    for config in user_configs:
        merged_config[config['key']] = config['value']

    # Collect all settings
    merged_settings = {}

    # Start with tenant settings (lower priority)
    tenant_settings = Settings.objects.filter(
        tenant=tenant,
        user__isnull=True
    ).values('key', 'value')

    for setting in tenant_settings:
        merged_settings[setting['key']] = setting['value']

    # Override with user settings
    user_settings = Settings.objects.filter(
        tenant=tenant,
        user=user
    ).values('key', 'value')

    for setting in user_settings:
        merged_settings[setting['key']] = setting['value']

    return Response({
        "user": {
            "id": str(user.id),
            "email": user.email,
            "role": user.role,
            "first_name": user.first_name,
            "last_name": user.last_name,
            "full_name": user.full_name
        },
        "tenant": {
            "id": str(tenant.id),
            "name": tenant.name,
            "website": tenant.website,
            "status": tenant.status
        },
        "config": merged_config,    # Merged configs with priority: user > tenant > global
        "settings": merged_settings # Merged settings with priority: user > tenant
    })

