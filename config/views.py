from django.contrib.auth.decorators import login_required
from django.contrib.auth import logout
from django.shortcuts import render

from masters.models import Item
from procurement.models import GRN, Site, BOMHeader
from ledger.models import StockLedgerEntry


@login_required
def dashboard_home(request):
    context = {
        "item_count": Item.objects.filter(is_active=True).count(),
        "bom_count": BOMHeader.objects.count(),
        "grn_count": GRN.objects.count(),
        "site_count": Site.objects.filter(is_active=True).count(),
        "ledger_count": StockLedgerEntry.objects.count(),
    }

    return render(request, "dashboard/home.html", context)


def user_logout(request):
    logout(request)
    return render(request, "registration/logout_done.html")