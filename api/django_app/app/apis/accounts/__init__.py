from rest_framework.routers import DefaultRouter

from .accounts_viewset import AccountsViewSet

router = DefaultRouter()
router.register(r'accounts', AccountsViewSet, basename='accounts')
urlpatterns = router.urls
