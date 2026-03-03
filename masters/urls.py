from django.urls import path
from . import views

urlpatterns = [
    path("api/group2/", views.api_group2, name="api_group2"),
    path("api/grades/", views.api_grades, name="api_grades"),
    path("api/items/", views.api_items, name="api_items"),
]