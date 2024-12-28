from rest_framework.routers import DefaultRouter

from .leads_viewset import LeadsViewSet

router = DefaultRouter()
router.register(r'leads', LeadsViewSet, basename='lead')
urlpatterns = router.urls
