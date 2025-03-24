"""
URL configuration for userport project.

The `urlpatterns` list routes URLs to views. For more information please see:
    https://docs.djangoproject.com/en/5.0/topics/http/urls/
Examples:
Function views
    1. Add an import:  from my_app import views
    2. Add a URL to urlpatterns:  path('', views.home, name='home')
Class-based views
    1. Add an import:  from other_app.views import Home
    2. Add a URL to urlpatterns:  path('', Home.as_view(), name='home')
Including another URLconf
    1. Import the include() function: from django.urls import include, path
    2. Add a URL to urlpatterns:  path('blog/', include('blog.urls'))
"""
from django.contrib import admin
from django.urls import path, include

from app.apis.auth.auth_urls import authurlpatterns
from app.apis.custom_column import urlpatterns as customcolumnurlpatterns
from app.apis.health.health_urls import healthurlpatterns
from app.apis.tenants.tenant_urls import urlpatterns as tenanturlpatterns
from app.apis.products import urlpatterns as producturlpatterns
from app.apis.leads import urlpatterns as leadsurlpatterns
from app.apis.accounts import urlpatterns as accountsurlpatterns
from app.apis.config import urlpatterns as configandsettingsurlpatterns

urlpatterns = [
    path('admin/', admin.site.urls),
    path('api/v2/', include([
        path('', include(authurlpatterns)),
        path('', include(healthurlpatterns)),
        path('', include(tenanturlpatterns)),
        path('', include(producturlpatterns)),
        path('', include(leadsurlpatterns)),
        path('', include(accountsurlpatterns)),
        path('', include(configandsettingsurlpatterns)),
        path('', include(customcolumnurlpatterns)),
    ])),
]
