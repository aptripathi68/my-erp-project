from django.contrib import admin
from django.urls import path, include
from config.views import dashboard_home


urlpatterns = [
    # ERP Dashboard (main landing page)
    path("", dashboard_home, name="dashboard_home"),

    # Django Admin (for maintenance)
    path("admin/", admin.site.urls),

    # Masters APIs
    path("api/masters/", include("masters.urls")),

    # Ledger APIs
    path("api/", include("ledger.urls")),

    # Procurement APIs
    path("procurement/", include("procurement.urls")),
]