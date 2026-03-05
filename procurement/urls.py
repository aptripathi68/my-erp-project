# procurement/urls.py
from django.urls import path
from .views_bom import bom_upload, bom_export_master

urlpatterns = [
    path("bom/upload/", bom_upload, name="bom_upload"),
    path("bom/<int:bom_id>/export-master/", bom_export_master, name="bom_export_master"),
]