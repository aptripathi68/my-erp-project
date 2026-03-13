from django.contrib.auth.decorators import login_required
from django.contrib.auth import logout
from django.shortcuts import render

from masters.models import Item
from procurement.models import GRN, Site, BOMHeader
from ledger.models import StockLedgerEntry
from drawings.models import DrawingSheetRevision
from procurement.models import BOMMark


@login_required
def dashboard_home(request):

    drawings_uploaded = DrawingSheetRevision.objects.count()

    pending_drawing_approvals = DrawingSheetRevision.objects.filter(
        verification_status="PENDING"
    ).count()

    total_marks = BOMMark.objects.count()

    context = {
        "drawings_uploaded": drawings_uploaded,
        "pending_drawing_approvals": pending_drawing_approvals,
        "bom_count": BOMHeader.objects.count(),
        "total_marks": total_marks,
    }

    return render(request, "dashboard/home.html", context)


def user_logout(request):
    logout(request)
    return render(request, "registration/logout_done.html")