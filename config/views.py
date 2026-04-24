from django.contrib.auth.decorators import login_required
from django.contrib.admin.views.decorators import staff_member_required
from django.contrib.auth import logout
from django.shortcuts import redirect, render

from drawings.models import Drawing, DrawingSheetRevision
from masters.models import Item
from procurement.models import GRN, Site, BOMHeader, BOMMark
from ledger.models import StockLedgerEntry


@login_required
def dashboard_home(request):

    projects = BOMHeader.objects.all()

    project_status = []

    for project in projects:

        marks = BOMMark.objects.filter(bom=project)

        total_marks = marks.count()

        fabrication = marks.filter(production_status=BOMMark.ProductionStatus.IN_FABRICATION).count()
        painting = marks.filter(production_status=BOMMark.ProductionStatus.IN_PAINTING).count()
        dispatch_ready = marks.filter(production_status=BOMMark.ProductionStatus.DISPATCH_READY).count()
        dispatched = marks.filter(production_status=BOMMark.ProductionStatus.DISPATCHED).count()

        planning_pending = marks.filter(production_status=BOMMark.ProductionStatus.PLANNING_PENDING).count()

        project_status.append({
            "project": project.project_name if hasattr(project, "project_name") else f"BOM-{project.id}",
            "total": total_marks,
            "planning": planning_pending,
            "fabrication": fabrication,
            "painting": painting,
            "ready": dispatch_ready,
            "dispatched": dispatched,
        })

    context = {
        "item_count": Item.objects.filter(is_active=True).count(),
        "bom_count": BOMHeader.objects.count(),
        "grn_count": GRN.objects.count(),
        "site_count": Site.objects.filter(is_active=True).count(),
        "ledger_count": StockLedgerEntry.objects.count(),
        "drawings_uploaded": Drawing.objects.count(),
        "pending_drawing_approvals": DrawingSheetRevision.objects.filter(
            verification_status=DrawingSheetRevision.STATUS_PENDING
        ).count(),
        "total_marks": BOMMark.objects.count(),
        "projects": project_status,
    }

    return render(request, "dashboard/home.html", context)


def user_logout(request):
    logout(request)
    return render(request, "registration/logout_done.html")


@staff_member_required
def admin_bom_upload(request):
    return redirect("procurement:bom_upload")


@staff_member_required
def admin_drawing_upload(request):
    return redirect("drawings:upload_from_bom")


@staff_member_required
def admin_bulk_drawing_upload(request):
    return redirect("drawings:bulk_upload")
