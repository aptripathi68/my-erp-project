from django import forms

from procurement.models import BOMHeader, BOMMark


class DrawingUploadSelectForm(forms.Form):
    bom = forms.ModelChoiceField(
        queryset=BOMHeader.objects.all().order_by("-id"),
        label="Select BOM Record",
        help_text="Choose the BOM record first. Drawing numbers will be loaded from this BOM.",
    )

    drawing_no = forms.ChoiceField(
        choices=[],
        required=False,
        label="Drawing Number",
        help_text="Select a drawing number from the chosen BOM.",
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

    def __init__(self, *args, **kwargs):
        super().__init__(*args, **kwargs)

        bom = None

        if self.is_bound:
            bom_id = self.data.get("bom")
            if bom_id:
                try:
                    bom = BOMHeader.objects.get(pk=bom_id)
                except BOMHeader.DoesNotExist:
                    bom = None
        else:
            bom = self.initial.get("bom")

        if bom:
            drawing_nos = (
                BOMMark.objects.filter(bom=bom)
                .exclude(drawing_no__isnull=True)
                .exclude(drawing_no__exact="")
                .values_list("drawing_no", flat=True)
                .distinct()
                .order_by("drawing_no")
            )
            self.fields["drawing_no"].choices = [(d, d) for d in drawing_nos]
        else:
            self.fields["drawing_no"].choices = []

    def clean(self):
        cleaned_data = super().clean()
        bom = cleaned_data.get("bom")
        drawing_no = cleaned_data.get("drawing_no")

        if bom and drawing_no:
            exists = BOMMark.objects.filter(
                bom=bom,
                drawing_no=drawing_no,
            ).exists()
            if not exists:
                raise forms.ValidationError("Selected drawing number does not belong to the selected BOM.")

        return cleaned_data