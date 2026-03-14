from django.urls import path
from . import views

app_name = "drawings"

urlpatterns = [

    # Home
    path(
        "",
        views.home,
        name="home"
    ),

    # Upload drawing linked to BOM
    path(
        "upload-from-bom/",
        views.upload_from_bom,
        name="upload_from_bom"
    ),

    # Revision detail (preview / verify screen)
    path(
        "revision/<int:pk>/",
        views.revision_detail,
        name="revision_detail"
    ),

    # Confirm drawing revision
    path(
        "revision/<int:pk>/confirm/",
        views.confirm_revision,
        name="confirm_revision"
    ),

    # Reject drawing revision
    path(
        "revision/<int:pk>/reject/",
        views.reject_revision,
        name="reject_revision"
    ),

    # AJAX endpoint → get drawing numbers from BOM
    path(
        "ajax/bom-drawing-numbers/",
        views.bom_drawing_numbers,
        name="bom_drawing_numbers"
    ),
        
    # Bulk drawing upload (ZIP / PDF bundle)
    path(
        "bulk-upload/",
        views.bulk_upload,
        name="bulk_upload"
    ),

]