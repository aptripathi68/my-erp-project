from django.urls import path
from . import views

app_name = "ledger"

urlpatterns = [
    path("", views.inventory_dashboard, name="inventory_dashboard"),
    path("locations/create/", views.create_location, name="create_location"),
    path("locations/<int:location_id>/edit/", views.edit_location, name="edit_location"),
    path("locations/<int:location_id>/delete/", views.delete_location, name="delete_location"),
    path("locations/<int:location_id>/permanent-delete/", views.permanent_delete_location, name="permanent_delete_location"),
    path("locations/<int:location_id>/transfer-records/", views.transfer_store_records, name="transfer_store_records"),
    path("inventory/inward/create/", views.create_inventory_inward, name="create_inventory_inward"),
    path("temporary-issues/create/", views.create_temporary_issue, name="create_temporary_issue"),
    path("temporary-returns/create/", views.create_temporary_return, name="create_temporary_return"),
    path("stock/export/store-items.xlsx", views.export_store_stock_excel, name="export_store_stock_excel"),

    path("stock/by-item/", views.api_stock_by_item, name="api_stock_by_item"),
    path("stock/by-location/", views.api_stock_by_location, name="api_stock_by_location"),
    path("stock/by-mark/", views.api_stock_by_mark, name="api_stock_by_mark"),
    path("stock/by-qr/", views.api_stock_by_qr, name="api_stock_by_qr"),

    path("offcuts/capture/", views.api_offcut_capture, name="api_offcut_capture"),

    path("offcuts/<str:qr_code>/", views.api_offcut_detail, name="api_offcut_detail"),
]
