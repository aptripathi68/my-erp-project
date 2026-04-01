from django.contrib import admin
from django.urls import path, include
from django.conf import settings
from django.conf.urls.static import static
from django.contrib.auth import views as auth_views
from config.views import (
    admin_bom_upload,
    admin_bulk_drawing_upload,
    admin_drawing_upload,
    dashboard_home,
    user_logout,
)

urlpatterns = [
    path("", dashboard_home, name="dashboard_home"),

    path("admin/bom-upload/", admin_bom_upload, name="admin_bom_upload"),
    path("admin/drawing-upload/", admin_drawing_upload, name="admin_drawing_upload"),
    path(
        "admin/bulk-drawing-upload/",
        admin_bulk_drawing_upload,
        name="admin_bulk_drawing_upload",
    ),

    path("admin/", admin.site.urls),

    path(
        "login/",
        auth_views.LoginView.as_view(template_name="registration/login.html"),
        name="login"
    ),

    path(
        "logout/",
        user_logout,
        name="logout"
    ),

    path("", include("masters.urls")),
    path("api/", include("ledger.urls")),
    path("procurement/", include("procurement.urls")),
    path("drawings/", include("drawings.urls")),
    path("estimation/", include("estimation.urls")),
]

if settings.DEBUG:
    urlpatterns += static(settings.MEDIA_URL, document_root=settings.MEDIA_ROOT)
