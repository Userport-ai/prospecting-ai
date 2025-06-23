# urls.py
from django.urls import path, include
from rest_framework.routers import DefaultRouter
from .config_apis import ConfigViewSet, SettingsViewSet, get_merged_context

router = DefaultRouter()
router.register(r'configs', ConfigViewSet, basename='configs')
router.register(r'settings', SettingsViewSet, basename='settings')

urlpatterns = [
    path('', include(router.urls)),
    path('context/', get_merged_context, name='user-context'),
]