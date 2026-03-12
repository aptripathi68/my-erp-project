from django import forms
from django.contrib import admin, messages
from django.utils import timezone
from django.utils.html import format_html
from django.urls import path, reverse
from django.shortcuts import get_object_or_404, redirect

from .models import Drawing, DrawingSheet, DrawingSheetRevision
from .services import create_or_update_sheet_revision
from .storage import generate_presigned_download_url
from django.utils.html import format_html, format_html_join


class DrawingSheetRevisionAdminForm(forms.ModelForm):
    upload_file = forms.FileField(required=False, help_text="Upload drawing PDF")

    class Meta:
        model = DrawingSheetRevision
        fields = "__all__"

    def __init__(self, *args, **kwargs):
        super().__init__(*args, **kwargs)

        optional_if_present = [
            "file_key",
            "original_filename",
            "content_type",
            "file_size",
            "uploaded_by",
            "verified_by",
            "verified_at",
            "verification_status",
        ]
        for field_name in optional_if_present:
            if field_name in self.fields:
                self.fields[field_name].required = False

    def clean(self):
        cleaned_data = super().clean()
        upload_file = cleaned_data.get("upload_file")
        file_key = cleaned_data.get("file_key")

        if not self.instance.pk and not upload_file and not file_key:
            raise forms.ValidationError("Please select an upload file.")

        return cleaned_data


class DrawingSheetRevisionInline(admin.TabularInline):
    model = DrawingSheetRevision
    extra = 0
    fields = (
        "revision_no",
        "verification_status",
        "is_current",
        "uploaded_at",
    )
    readonly_fields = ("uploaded_at",)
    show_change_link = True


class DrawingSheetInline(admin.TabularInline):
    model = DrawingSheet
    extra = 0
    fields = ("sheet_no",)
    show_change_link = True


@admin.register(Drawing)
class DrawingAdmin(admin.ModelAdmin):
    list_display = (
        "drawing_no",
        "title",
        "project",
        "created_at",
    )
    search_fields = (
        "drawing_no",
        "title",
    )
    list_filter = ("project",)
    inlines = [DrawingSheetInline]


@admin.register(DrawingSheet)
class DrawingSheetAdmin(admin.ModelAdmin):
    list_display = (
        "drawing",
        "sheet_no",
    )
    search_fields = (
        "drawing__drawing_no",
        "drawing__title",
        "sheet_no",
    )
    inlines = [DrawingSheetRevisionInline]


@admin.register(DrawingSheetRevision)
class DrawingSheetRevisionAdmin(admin.ModelAdmin):
    form = DrawingSheetRevisionAdminForm

    list_display = (
        "drawing_sheet",
        "revision_no",
        "verification_status",
        "is_current",
        "uploaded_by",
        "uploaded_at",
        "download_link",
        "action_buttons",
    )
    search_fields = (
        "drawing_sheet__drawing__drawing_no",
        "drawing_sheet__drawing__title",
        "drawing_sheet__sheet_no",
        "revision_no",
    )
    list_filter = (
        "verification_status",
        "is_current",
        "uploaded_at",
    )
    readonly_fields = (
        "file_key",
        "original_filename",
        "content_type",
        "file_size",
        "uploaded_by",
        "uploaded_at",
        "verified_by",
        "verified_at",
        "verification_status",
        "download_link",
        "action_buttons",
    )

    fieldsets = (
        (
            "Revision Info",
            {
                "fields": (
                    "drawing_sheet",
                    "revision_no",
                    "is_current",
                    "upload_file",
                )
            },
        ),
        (
            "Verification",
            {
                "fields": (
                    "verification_status",
                    "verified_by",
                    "verified_at",
                    "action_buttons",
                )
            },
        ),
        (
            "Stored File Metadata",
            {
                "classes": ("collapse",),
                "fields": (
                    "file_key",
                    "original_filename",
                    "content_type",
                    "file_size",
                    "uploaded_by",
                    "uploaded_at",
                    "download_link",
                ),
            },
        ),
    )

    def get_urls(self):
        urls = super().get_urls()
        custom_urls = [
            path(
                "<int:revision_id>/confirm/",
                self.admin_site.admin_view(self.confirm_revision_view),
                name="drawings_drawingsheetrevision_confirm",
            ),
            path(
                "<int:revision_id>/reject/",
                self.admin_site.admin_view(self.reject_revision_view),
                name="drawings_drawingsheetrevision_reject",
            ),
        ]
        return custom_urls + urls

    def download_link(self, obj):
        if not obj.pk or not obj.file_key:
            return "-"
        try:
            url = generate_presigned_download_url(obj.file_key)
            return format_html('<a href="{}" target="_blank">Preview / Download</a>', url)
        except Exception:
            return "Download unavailable"

    download_link.short_description = "Preview"

    def action_buttons(self, obj):
        if not obj.pk:
            return "-"

        buttons = []

        if obj.file_key:
            try:
                preview_url = generate_presigned_download_url(obj.file_key)
                buttons.append(
                    f'<a class="button" href="{preview_url}" target="_blank">Preview</a>'
                )
            except Exception:
                pass

        if obj.verification_status == DrawingSheetRevision.STATUS_PENDING:
            confirm_url = reverse(
                "admin:drawings_drawingsheetrevision_confirm",
                args=[obj.pk],
            )
            reject_url = reverse(
                "admin:drawings_drawingsheetrevision_reject",
                args=[obj.pk],
            )

            buttons.append(f'<a class="button" href="{confirm_url}">Confirm</a>')
            buttons.append(f'<a class="button" href="{reject_url}">Reject</a>')

        if not buttons:
            return "-"

        return format_html_join(" ", "{}", ((button,) for button in buttons))

    action_buttons.short_description = "Actions"

    def confirm_revision_view(self, request, revision_id):
        obj = get_object_or_404(DrawingSheetRevision, pk=revision_id)

        obj.verification_status = DrawingSheetRevision.STATUS_VERIFIED
        obj.verified_by = request.user
        obj.verified_at = timezone.now()
        obj.is_current = True
        obj.save()

        self.message_user(request, "Drawing revision confirmed and activated.", level=messages.SUCCESS)
        change_url = reverse("admin:drawings_drawingsheetrevision_change", args=[obj.pk])
        return redirect(change_url)

    def reject_revision_view(self, request, revision_id):
        obj = get_object_or_404(DrawingSheetRevision, pk=revision_id)

        obj.verification_status = DrawingSheetRevision.STATUS_REJECTED
        obj.verified_by = request.user
        obj.verified_at = timezone.now()
        obj.is_current = False
        obj.save()

        self.message_user(request, "Drawing revision rejected. Please re-upload correct file.", level=messages.WARNING)
        change_url = reverse("admin:drawings_drawingsheetrevision_change", args=[obj.pk])
        return redirect(change_url)

    def save_model(self, request, obj, form, change):
        upload_file = form.cleaned_data.get("upload_file")

        if upload_file:
            revision = create_or_update_sheet_revision(
                drawing_no=obj.drawing_sheet.drawing.drawing_no,
                title=obj.drawing_sheet.drawing.title,
                project=obj.drawing_sheet.drawing.project,
                sheet_no=obj.drawing_sheet.sheet_no,
                revision_no=obj.revision_no,
                uploaded_file=upload_file,
                uploaded_by=request.user,
            )
            obj.pk = revision.pk
            messages.success(
                request,
                "Drawing revision uploaded to Cloudflare R2 successfully. Please Preview and Confirm before production use.",
            )
            return

        if not obj.uploaded_by_id:
            obj.uploaded_by = request.user

        super().save_model(request, obj, form, change)