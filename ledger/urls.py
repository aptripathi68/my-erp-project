from django.urls import path
from . import views

urlpatterns = [
    path("stock/by-item/", views.api_stock_by_item, name="api_stock_by_item"),
    path("stock/by-location/", views.api_stock_by_location, name="api_stock_by_location"),
    path("stock/by-mark/", views.api_stock_by_mark, name="api_stock_by_mark"),
    path("stock/by-qr/", views.api_stock_by_qr, name="api_stock_by_qr"),

    path("offcuts/capture/", views.api_offcut_capture, name="api_offcut_capture"),

    path("offcuts/<str:qr_code>/", views.api_offcut_lookup, name="api_offcut_lookup"),
]