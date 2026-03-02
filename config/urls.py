
"""
URL configuration for config project.
"""
from django.contrib import admin
from django.urls import path
from django.http import HttpResponse

# Simple home view
def home(request):
    return HttpResponse("""
        <h1>ERP System</h1>
        <p>Welcome to your inventory management system.</p>
        <p><a href="/admin/">Go to Admin</a></p>
    """)

urlpatterns = [
    path('', home, name='home'),
    path('admin/', admin.site.urls),
]