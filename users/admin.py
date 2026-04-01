from django.contrib import admin

# Register your models here.
from django.contrib import admin
from django.contrib.auth.admin import UserAdmin
from .models import User

@admin.register(User)
class CustomUserAdmin(UserAdmin):
    list_display = ['username', 'email', 'role', 'is_staff']
    list_filter = ['role', 'is_staff']
    
    fieldsets = UserAdmin.fieldsets + (
        ('Additional Info', {'fields': ('role', 'phone', 'employee_id')}),
    )
    
    add_fieldsets = UserAdmin.add_fieldsets + (
        ('Permissions', {'fields': ('is_staff', 'is_superuser')}),
        ('Additional Info', {'fields': ('role', 'phone', 'employee_id')}),
    )
