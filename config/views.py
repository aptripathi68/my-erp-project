from django.contrib.auth.decorators import login_required
from django.contrib.auth import logout
from django.shortcuts import render

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

        fabrication = marks.filter(production_status="FABRICATION").count()
        painting = marks.filter(production_status="PAINTING").count()
        dispatch_ready = marks.filter(production_status="READY").count()
        dispatched = marks.filter(production_status="DISPATCHED").count()

        planning_pending = marks.filter(production_status="PLANNING").count()

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
        "projects": project_status,
    }

    return render(request, "dashboard/home.html", context)


def user_logout(request):
    logout(request)
    return render(request, "registration/logout_done.html")