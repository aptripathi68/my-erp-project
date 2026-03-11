from django.contrib import admin
from django.urls import path, include
from django.conf import settings
from django.conf.urls.static import static
from django.contrib.auth import views as auth_views
from config.views import dashboard_home, user_logout

urlpatterns = [
    path("", dashboard_home, name="dashboard_home"),

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
]

if settings.DEBUG:
    urlpatterns += static(settings.MEDIA_URL, document_root=settings.MEDIA_ROOT)