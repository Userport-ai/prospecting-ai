from django.urls import path, include
from rest_framework.routers import DefaultRouter

from app.apis.custom_column.custom_column_viewset import CustomColumnViewSet, LeadCustomColumnValueViewSet, \
    AccountCustomColumnValueViewSet

router = DefaultRouter()
router.register('custom_columns', CustomColumnViewSet, basename='custom-columns')
router.register('lead_column_values', LeadCustomColumnValueViewSet, basename='lead-column-values')
router.register('account_column_values', AccountCustomColumnValueViewSet, basename='account-column-values')

urlpatterns = [
    path('', include(router.urls)),
]