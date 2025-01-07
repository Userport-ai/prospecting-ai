from rest_framework.routers import DefaultRouter
from django.urls import path
from .accounts_viewset import AccountsViewSet
from .enrichment_callback import enrichment_callback

from .accounts_viewset import AccountsViewSet

router = DefaultRouter()
router.register(r'accounts', AccountsViewSet, basename='accounts')
urlpatterns = router.urls
urlpatterns += [
    path('internal/enrichment-callback/', enrichment_callback, name='enrichment_callback'),
]