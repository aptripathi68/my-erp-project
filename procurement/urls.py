from django.urls import path
from . import views_bom

app_name = "procurement"

urlpatterns = [
    path("planning/", views_bom.planning_dashboard, name="planning_dashboard"),
    path("planning/bom/<int:bom_id>/", views_bom.planning_bom_detail, name="planning_bom_detail"),
    path("planning/bom/<int:bom_id>/generate-int-erc/", views_bom.generate_bom_int_erc, name="generate_bom_int_erc"),
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
