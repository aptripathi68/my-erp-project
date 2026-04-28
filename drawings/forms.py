from django import forms

from drawings.models import Drawing, DrawingSheet, DrawingSheetRevision


class DrawingUploadSelectForm(forms.Form):
    drawing_no = forms.CharField(
        max_length=100,
        label="Drawing Number",
        help_text="Enter the drawing number exactly as shown on the drawing.",
    )
    title = forms.CharField(
        max_length=255,
        required=False,
        label="Drawing Title",
    )
    sheet_no = forms.CharField(
        max_length=20,
        label="Sheet No",
    )
    revision_no = forms.CharField(
        max_length=50,
        label="Revision No",
    )
    upload_file = forms.FileField(
        label="Drawing PDF",
    )

    def clean(self):
        cleaned_data = super().clean()
        drawing_no = (cleaned_data.get("drawing_no") or "").strip()
        sheet_no = (cleaned_data.get("sheet_no") or "").strip()
        revision_no = (cleaned_data.get("revision_no") or "").strip()

        if drawing_no and sheet_no and revision_no:
            drawing = Drawing.objects.filter(project__isnull=True, drawing_no=drawing_no).first()
            if drawing:
                sheet = DrawingSheet.objects.filter(drawing=drawing, sheet_no=sheet_no).first()
                if sheet:
                    existing_revision = DrawingSheetRevision.objects.filter(
                        drawing_sheet=sheet,
                        revision_no=revision_no,
                    ).first()
                    if existing_revision and existing_revision.verification_status != DrawingSheetRevision.STATUS_REJECTED:
                        raise forms.ValidationError(
                            "This sheet revision already exists. Please upload a new revision number."
                        )

        return cleaned_data


class BulkDrawingUploadForm(forms.Form):
    upload_file = forms.FileField(
        label="ZIP / PDF Bundle",
        help_text="Upload one ZIP file or one multi-page PDF bundle.",
    )
    batch_name = forms.CharField(
        max_length=255,
        required=False,
        label="Batch Name",
        help_text="Optional name for this upload batch.",
    )
