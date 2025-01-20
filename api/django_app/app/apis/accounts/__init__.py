from django.urls import path
from rest_framework.routers import DefaultRouter

from app.apis.common.enrichment_callback import enrichment_callback
from .accounts_viewset import AccountsViewSet
from .accounts_viewset import AccountsViewSet

router = DefaultRouter()
router.register(r'accounts', AccountsViewSet, basename='accounts')
urlpatterns = router.urls
urlpatterns += [
    path('internal/enrichment-callback/', enrichment_callback, name='enrichment_callback'),
]