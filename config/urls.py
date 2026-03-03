from django.contrib import admin
from django.urls import path
from django.http import HttpResponse
from masters import views as masters_views

def home(request):
    return HttpResponse("""
        <h1>ERP System</h1>
        <p>Welcome to your inventory management system.</p>
        <p><a href="/admin/">Go to Admin</a></p>
    """)

urlpatterns = [
    path("", home, name="home"),
    path("admin/", admin.site.urls),

    # API endpoints for cascading selection
    path("api/group2/", masters_views.api_group2, name="api_group2"),
    path("api/grades/", masters_views.api_grades, name="api_grades"),
    path("api/items/", masters_views.api_items, name="api_items"),
]