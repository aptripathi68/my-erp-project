from django.contrib import admin

# Register your models here.
from django.contrib import admin
from django.http import HttpResponse
from django.urls import path
from django.shortcuts import render, redirect
from django.contrib import messages
from django import forms
from .models import Group2, Grade, Item
from .utils.excel_import import ItemMasterImporter

class ExcelImportForm(forms.Form):
    excel_file = forms.FileField(
        label='Select Excel File',
        help_text='Upload Excel file with Group2, Grade, Item Code, Description columns'
    )
    
    class Meta:
        widgets = {
            'excel_file': forms.FileInput(attrs={'accept': '.xlsx,.xls'})
        }


@admin.register(Group2)
class Group2Admin(admin.ModelAdmin):
    list_display = ['code', 'name', 'grade_count', 'item_count']
    search_fields = ['code', 'name']
    
    def grade_count(self, obj):
        return obj.grades.count()
    grade_count.short_description = 'Grades'
    
    def item_count(self, obj):
        return Item.objects.filter(group2=obj).count()
    item_count.short_description = 'Items'


@admin.register(Grade)
class GradeAdmin(admin.ModelAdmin):
    list_display = ['code', 'name', 'group2', 'item_count']
    list_filter = ['group2']
    search_fields = ['code', 'name']
    
    def item_count(self, obj):
        return obj.items.count()
    item_count.short_description = 'Items'


@admin.register(Item)
class ItemAdmin(admin.ModelAdmin):
    list_display = ['item_master_id', 'item_description', 'group2', 'grade', 'unit_weight', 'is_active']
    list_filter = ['group2', 'grade', 'is_active', 'import_batch_id']
    search_fields = ['item_master_id', 'item_description', 'hsn_code']
    list_editable = ['is_active']
    
    def get_urls(self):
        urls = super().get_urls()
        custom_urls = [
            path('import-excel/', self.admin_site.admin_view(self.import_excel), name='masters_item_import'),
        ]
        return custom_urls + urls
    
    def import_excel(self, request):
        from django.http import HttpResponse
        return HttpResponse("Import page is working! Your template issue is fixed.")