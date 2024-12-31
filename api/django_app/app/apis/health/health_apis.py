from django.http import JsonResponse
from django.db import connections
from django.db.utils import OperationalError
import logging
import psutil
import time

from rest_framework.decorators import permission_classes, api_view, authentication_classes
from rest_framework.permissions import AllowAny

logger = logging.getLogger(__name__)


def check_database():
    """Check if database connections are working."""
    try:
        for name in connections.databases:
            cursor = connections[name].cursor()
            cursor.execute("SELECT 1")
            row = cursor.fetchone()
            if row is None:
                return False
    except OperationalError:
        return False
    return True


def check_system_resources():
    """Check system resources like CPU, memory, and disk space."""
    try:
        cpu_usage = psutil.cpu_percent(interval=1)
        memory = psutil.virtual_memory()
        disk = psutil.disk_usage('/')

        return {
            'cpu_usage': cpu_usage,
            'memory_usage': memory.percent,
            'disk_usage': disk.percent,
        }
    except Exception as e:
        logger.error(f"Error checking system resources: {str(e)}")
        return None


@api_view(['GET', 'POST'])
@permission_classes([AllowAny])
@authentication_classes([])
def health_check(request):
    """
    Main health check endpoint that returns the status of various components.
    """
    start_time = time.time()

    # Check database
    db_status = check_database()

    # Check system resources
    system_resources = check_system_resources()

    # Calculate response time
    response_time = (time.time() - start_time) * 1000  # Convert to milliseconds

    status = {
        'status': 'healthy' if db_status else 'unhealthy',
        'database': {
            'status': 'up' if db_status else 'down',
        },
        'system_resources': system_resources,
        'response_time_ms': round(response_time, 2)
    }

    # If any critical service is down, return 503
    http_status = 200 if db_status else 503

    return JsonResponse(status, status=http_status)


@api_view(['GET', 'POST'])
@permission_classes([AllowAny])
@authentication_classes([])
def db_readiness_check(request):
    """
    Readiness check endpoint to determine if the application is ready to serve traffic.
    """
    # Check critical services
    db_status = check_database()

    status = {
        'status': 'ready' if db_status else 'not_ready',
        'database': db_status
    }

    http_status = 200 if status['status'] == 'ready' else 503
    return JsonResponse(status, status=http_status)


@api_view(['GET', 'POST'])
@permission_classes([AllowAny])
@authentication_classes([])
def liveness_check(request):
    """
    Liveness check endpoint to determine if the application is running.
    """
    return JsonResponse({'status': 'alive'}, status=200)
