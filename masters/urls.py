from django.urls import path
from . import views

urlpatterns = [
    path("api/group2/", views.api_group2),
    path("api/grades/", views.api_grades),
    path("api/items/", views.api_items),

    path("item-master/", views.item_master_list, name="item_master_list"),
    path("item-master/add/", views.item_master_add, name="item_master_add"),
    path("item-master/<int:item_id>/edit/", views.item_master_edit, name="item_master_edit"),
]