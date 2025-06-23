import logging

logger = logging.getLogger(__name__)

import logging
from django.db import transaction
from firebase_admin import auth as firebase_auth
from rest_framework import viewsets, status
from rest_framework.decorators import action
from rest_framework.response import Response

from app.apis.common.base import TenantScopedViewSet
from app.models import Tenant, User, UserRole
from app.models.serializers.tenant_serializers import (
    TenantCreateSerializer,
    TenantSerializer,
    TenantUserSerializer
)
from app.models.users import UserStatus
from app.permissions import HasRole, IsInternalAdmin

logger = logging.getLogger(__name__)


class TenantViewSet(viewsets.ModelViewSet):
    """
    ViewSet for managing tenants.
    - GET: Internal admins can see all tenants, tenant admins can see their own tenant
    - POST/PUT/DELETE: Only internal admins can modify tenants
    """
    logger.debug("TenantViewSet initialization")
    serializer_class = TenantSerializer
    queryset = Tenant.objects.all()
    permission_classes = [IsInternalAdmin]

    def get_queryset(self):
        queryset = super().get_queryset()
        # Filter queryset for tenant admins to only show their tenant
        if (
                self.request.user.role == UserRole.TENANT_ADMIN.value
                and hasattr(self.request.user, 'tenant')
        ):
            queryset = queryset.filter(id=self.request.user.tenant.id)
        return queryset

    def get_serializer_class(self):
        if self.action == 'create':
            logger.debug("Creating tenant...")
            return TenantCreateSerializer
        return self.serializer_class

    def check_permissions(self, request):
        if request.method not in ['GET', 'HEAD', 'OPTIONS']:
            if not IsInternalAdmin().has_permission(request, self):
                self.permission_denied(request)
        return super().check_permissions(request)

    @action(detail=True, methods=['post'], url_path='invite-user')
    @transaction.atomic
    def invite_user(self, request, pk=None):
        """
        Invite a user to the tenant. Creates a new Firebase user if they don't exist
        and sends an email invitation with a sign-in link.
        """
        logger.debug("Inviting user...")
        tenant = self.get_object()
        email = request.data.get('email')
        role = request.data.get('role')

        # Input validation
        if not email or not role:
            return Response(
                {"error": "Email and role are required"},
                status=status.HTTP_400_BAD_REQUEST
            )

        if role not in UserRole.values:
            return Response(
                {"error": "Invalid role"},
                status=status.HTTP_400_BAD_REQUEST
            )

        try:
            # Try to get existing Firebase user
            try:
                firebase_user = firebase_auth.get_user_by_email(email)
                logger.debug(f"Found existing Firebase user: {email}")
                is_new_user = False
            except firebase_auth.UserNotFoundError:
                # Create new Firebase user without password
                firebase_user = firebase_auth.create_user(
                    email=email,
                    email_verified=False
                )
                logger.debug(f"Created new Firebase user: {email}")
            logger.debug(
                f"Available UserStatus values: {UserStatus.choices}")  # This will show all valid status choices
            is_new_user = True

            # TODO: Send invitation email with action_link using your email service
            logger.info(f"Sign-in link generated for new user: {email}")

            # Log available status values for debugging
            logger.debug(f"Available UserStatus values: {UserStatus.__members__}")

            # Create or update user in your database
            user, created = User.objects.get_or_create(
                firebase_id=firebase_user.uid,
                defaults={
                    'email': email,
                    'role': role,
                    'tenant': tenant,
                    'status': UserStatus.INACTIVE.value
                }
            )

            if not created:
                # Update existing user
                user.role = role
                user.tenant = tenant
                user.save()
                logger.debug(f"Updated existing user: {email}")

            response_data = {
                'message': f'User {email} {"invited" if created else "updated"} successfully',
                'user_id': str(user.id),
                'is_new_user': is_new_user
            }

            return Response(response_data, status=status.HTTP_200_OK)

        except (firebase_auth.UserNotFoundError, firebase_auth.EmailAlreadyExistsError) as e:
            logger.error(f"Email already exists in Firebase: {email}")
            return Response({
                "error": "Email already registered in authentication system"
            }, status=status.HTTP_409_CONFLICT)

        except Exception as e:
            logger.error(f"Error inviting user: {str(e)}")
            return Response({
                "error": "Failed to invite user",
                "details": str(e)
            }, status=status.HTTP_500_INTERNAL_SERVER_ERROR)


class TenantUserViewSet(TenantScopedViewSet):
    """
    ViewSet for managing users within a tenant.
    """
    serializer_class = TenantUserSerializer
    queryset = User.objects.all()

    def get_permissions(self):
        return [HasRole(allowed_roles=[UserRole.TENANT_ADMIN.value, UserRole.INTERNAL_ADMIN.value])]

    def get_queryset(self):
        queryset = super().get_queryset()
        role = self.request.query_params.get('role')
        if role:
            queryset = queryset.filter(role=role)
        return queryset

    @action(detail=True, methods=['patch'], url_path='update-role')
    @transaction.atomic
    def update_role(self, request, pk=None):
        """
        Update a user's role within the tenant
        """
        user = self.get_object()
        new_role = request.data.get('role')

        if new_role not in UserRole.values:
            return Response(
                {"error": "Invalid role"},
                status=status.HTTP_400_BAD_REQUEST
            )

        user.role = new_role
        user.save()
        return Response(TenantUserSerializer(user).data)
