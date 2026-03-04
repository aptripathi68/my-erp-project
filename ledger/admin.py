from django.contrib import admin
from .models import (
    StockLocation,
    StockObject,
    StockTxn,
    StockTxnLine,
    StockLedgerEntry,
)


class StockTxnLineInline(admin.TabularInline):
    model = StockTxnLine
    extra = 1


@admin.register(StockTxn)
class StockTxnAdmin(admin.ModelAdmin):
    inlines = [StockTxnLineInline]


admin.site.register(StockLocation)
admin.site.register(StockObject)
admin.site.register(StockLedgerEntry)