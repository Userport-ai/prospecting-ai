from app.models import Tenant, User, UserRole
from app.models.users import UserStatus
from django.db import transaction
from firebase_admin import auth as firebase_auth
from rest_framework import serializers


class TenantSerializer(serializers.ModelSerializer):
    class Meta:
        model = Tenant
        fields = ['id', 'name', 'website', 'status', 'settings', 'created_at', 'updated_at']
        read_only_fields = ['id', 'created_at', 'updated_at']


"""
Create a new tenant with admin:

POST /api/v1/tenants/
Headers:
  Authorization: Bearer <firebase_token>
Body:
{
    "name": "Userport Corp",
    "website": "https://userport.ai",
    "admin_email": "john.doe@userport.ai",
    "admin_first_name": "John",
    "admin_last_name": "Doe"
}
"""

class TenantCreateSerializer(serializers.Serializer):
    name = serializers.CharField(max_length=255)
    website = serializers.URLField(max_length=255)
    admin_email = serializers.EmailField(write_only=True)
    admin_first_name = serializers.CharField(max_length=100, write_only=True)
    admin_last_name = serializers.CharField(max_length=100, write_only=True)

    @transaction.atomic
    def create(self, validated_data):
        admin_email = validated_data['admin_email']

        # First check if user exists and their tenant status
        existing_user = User.objects.filter(email=admin_email).first()
        if existing_user and existing_user.tenant_id:
            raise serializers.ValidationError({
                'admin_email': 'User is already associated with another tenant'
            })

        # Check/get Firebase user
        try:
            firebase_user = firebase_auth.get_user_by_email(admin_email)
            firebase_uid = firebase_user.uid
        except firebase_auth.UserNotFoundError:
            # Create new Firebase user if doesn't exist
            firebase_user = firebase_auth.create_user(
                email=admin_email,
                display_name=f"{validated_data['admin_first_name']} {validated_data['admin_last_name']}"
            )
            firebase_uid = firebase_user.uid

        # Create tenant
        tenant = Tenant.objects.create(
            name=validated_data['name'],
            website=validated_data['website']
        )

        try:
            if existing_user:
                # Update existing user with new tenant and role
                existing_user.tenant = tenant
                existing_user.role = UserRole.TENANT_ADMIN
                existing_user.status = UserStatus.ACTIVE
                existing_user.save()
            else:
                # Create new user
                User.objects.create(
                    firebase_id=firebase_uid,
                    email=admin_email,
                    first_name=validated_data['admin_first_name'],
                    last_name=validated_data['admin_last_name'],
                    role=UserRole.TENANT_ADMIN,
                    status=UserStatus.ACTIVE,
                    tenant=tenant
                )

            return tenant

        except Exception as e:
            # Rollback tenant creation if anything fails
            tenant.delete(hard=True)
            raise serializers.ValidationError(f"Failed to create tenant admin: {str(e)}")

    def to_representation(self, instance):
        """Convert tenant instance to response format."""
        return {
            'id': instance.id,
            'name': instance.name,
            'website': instance.website,
            'status': instance.status,
            'created_at': instance.created_at,
            'updated_at': instance.updated_at
        }


class TenantUserSerializer(serializers.ModelSerializer):
    class Meta:
        model = User
        fields = ['id', 'email', 'first_name', 'last_name', 'role', 'status', 'created_at']
        read_only_fields = ['id', 'created_at']


class TenantUserInviteSerializer(serializers.Serializer):
    email = serializers.EmailField()
    first_name = serializers.CharField(max_length=100)
    last_name = serializers.CharField(max_length=100)
    role = serializers.ChoiceField(choices=UserRole.choices)
