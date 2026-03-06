from django.contrib import admin
from django.urls import path, include
from django.conf import settings
from django.conf.urls.static import static
from config.views import dashboard_home

urlpatterns = [
    path("", dashboard_home, name="dashboard_home"),
    path("admin/", admin.site.urls),

    # ERP pages
    path("", include("masters.urls")),

    # APIs
    path("api/", include("ledger.urls")),
    path("procurement/", include("procurement.urls")),
]

if settings.DEBUG:
    urlpatterns += static(settings.MEDIA_URL, document_root=settings.MEDIA_ROOT)
    urlpatterns += static(settings.STATIC_URL, document_root=settings.STATIC_ROOT)