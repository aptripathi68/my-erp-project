from django.urls import path

from . import views

app_name = "estimation"

urlpatterns = [
    path("", views.estimate_list, name="estimate_list"),
    path("new/", views.estimate_create, name="estimate_create"),
    path("<int:project_id>/delete/", views.delete_estimate, name="delete_estimate"),
    path("<int:project_id>/", views.estimate_detail, name="estimate_detail"),
    path("<int:project_id>/raw-materials/tentative-bom/", views.import_tentative_bom, name="import_tentative_bom"),
    path("<int:project_id>/raw-materials/add/", views.add_raw_material_line, name="add_raw_material_line"),
    path("<int:project_id>/raw-materials/<int:line_id>/delete/", views.delete_raw_material_line, name="delete_raw_material_line"),
    path("<int:project_id>/suppliers/add/", views.add_project_supplier, name="add_project_supplier"),
    path("<int:project_id>/rates/update/", views.update_rate_sheet, name="update_rate_sheet"),
    path("<int:project_id>/rates/download/", views.download_rate_sheet, name="download_rate_sheet"),
    path("<int:project_id>/rates/upload/", views.upload_rate_sheet, name="upload_rate_sheet"),
    path("<int:project_id>/supplier-quotations/upload/", views.upload_supplier_quotation, name="upload_supplier_quotation"),
    path("<int:project_id>/cost-heads/update/", views.update_cost_heads, name="update_cost_heads"),
    path("<int:project_id>/notes/update/", views.update_department_notes, name="update_department_notes"),
    path("<int:project_id>/quotation/decision/", views.submit_management_decision, name="submit_management_decision"),
    path("<int:project_id>/quotation/export/excel/", views.export_quotation_excel, name="export_quotation_excel"),
    path("<int:project_id>/quotation/export/pdf/", views.export_quotation_pdf, name="export_quotation_pdf"),
    path("<int:project_id>/po-received/", views.mark_po_received, name="mark_po_received"),
    path("<int:project_id>/budget/close/", views.close_budget, name="close_budget"),
    path("<int:project_id>/expenses/add/", views.add_expense, name="add_expense"),
    path("expenses/<int:expense_id>/approve/", views.approve_expense, name="approve_expense"),
    path("suppliers/create/", views.create_supplier, name="create_supplier"),
]
