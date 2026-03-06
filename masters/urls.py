from django.urls import path
from . import views

urlpatterns = [

    # API endpoints
    path("api/group2/", views.api_group2),
    path("api/grades/", views.api_grades),
    path("api/items/", views.api_items),

    # ERP pages
    path("item-master/", views.item_master_list, name="item_master_list"),
]