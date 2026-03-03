from django.urls import path
from . import views

app_name = "masters"

urlpatterns = [
    path("api/grades/", views.api_grades, name="api_grades"),
    path("api/items/", views.api_items, name="api_items"),
]