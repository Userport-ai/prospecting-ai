from app.models import Tenant
from django.http import HttpRequest
from rest_framework.exceptions import ValidationError, PermissionDenied


class TenantMiddleware:
    """
    Middleware to handle tenant context based on X-Tenant-Id header
    """

    def __init__(self, get_response):
        self.get_response = get_response

    def __call__(self, request: HttpRequest):
        # Skip tenant check for certain paths if needed
        if TenantMiddleware._is_path_exempt(request):
            return self.get_response(request)

        tenant_id = request.headers.get('X-Tenant-Id')

        if not tenant_id:
            raise ValidationError({
                'error': 'AUTH_FAILED',
                'message': 'X-Tenant-Id header is required'
            })

        try:
            tenant = Tenant.objects.get(id=tenant_id)

            # Verify tenant is active
            if tenant.status != 'active':
                raise PermissionDenied({
                    'error': 'AUTH_FAILED',
                    'message': f'Tenant {tenant_id} is not active'
                })

            # Add tenant to request
            request.tenant = tenant

            # If user is authenticated, verify tenant access
            if hasattr(request, 'user') and request.user.is_authenticated:
                if request.user.tenant_id != tenant.id:
                    raise PermissionDenied({
                        'error': 'AUTH_FAILED',
                        'message': 'User does not have access to this tenant'
                    })

        except Tenant.DoesNotExist:
            raise ValidationError({
                'error': 'AUTH_FAILED',
                'message': f'Tenant {tenant_id} not found'
            })
        except ValueError:
            raise ValidationError({
                'error': 'AUTH_FAILED',
                'message': 'Invalid tenant ID format'
            })

        response = self.get_response(request)
        return response

    @staticmethod
    def _get_exempt_paths() -> list[str]:
        """Paths that don't require tenant verification"""
        return [
            '/api/v2/health',
            '/api/v2/auth',
            '/api/v2/tenants',
            '/api/v2/context',
        ]

    @staticmethod
    def _is_path_exempt(request) -> bool:
        """Check if the current path is exempt from tenant verification"""
        path = request.path
        return any(path.startswith(exempt_path) for exempt_path in TenantMiddleware._get_exempt_paths())
