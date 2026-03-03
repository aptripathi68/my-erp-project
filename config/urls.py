from django.contrib import admin
from django.urls import path, include
from django.http import HttpResponse


def home(request):
    return HttpResponse("""
        <h1>ERP System</h1>
        <p>Welcome to your inventory management system.</p>
        <p><a href="/admin/">Go to Admin</a></p>
    """)


urlpatterns = [
    path('', home, name='home'),
    path('admin/', admin.site.urls),

    # ADD THIS LINE
    path('', include('masters.urls')),
]