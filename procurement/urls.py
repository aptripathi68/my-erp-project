from django.urls import path
from . import views_bom

app_name = "procurement"

urlpatterns = [
    path("bom/upload/", views_bom.bom_upload, name="bom_upload"),
    path(
        "bom/validation-errors/download/",
        views_bom.download_bom_validation_errors,
        name="download_bom_validation_errors",
    ),
    path(
        "bom/<int:bom_id>/export-master/",
        views_bom.bom_export_master,
        name="bom_export_master",
    ),
    path("bom/<int:bom_id>/delete/", 
         views_bom.bom_delete, 
         name="bom_delete"),
]