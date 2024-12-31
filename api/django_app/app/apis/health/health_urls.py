from django.urls import path
from .health_apis import *

healthurlpatterns = [
    path('health/', health_check, name='health_check'),
    path('health/ready/', db_readiness_check, name='readiness_check'),
    path('health/status/', liveness_check, name='liveness_check'),
]