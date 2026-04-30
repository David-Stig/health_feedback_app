from django import forms

from .models import Facility


class FacilityForm(forms.ModelForm):
    class Meta:
        model = Facility
        fields = ["name", "district", "province"]
        widgets = {
            "name": forms.TextInput(attrs={"class": "form-control", "placeholder": "Facility name"}),
            "district": forms.TextInput(attrs={"class": "form-control", "placeholder": "District"}),
            "province": forms.TextInput(attrs={"class": "form-control", "placeholder": "Province"}),
        }

class BulkFacilityUploadForm(forms.Form):
    file = forms.FileField(
        help_text="Upload a CSV file with the columns: name, district, province.",
        widget=forms.ClearableFileInput(attrs={"class": "form-control", "accept": ".csv,text/csv"}),
    )

    def clean_file(self):
        upload = self.cleaned_data["file"]
        if not upload.name.lower().endswith(".csv"):
            raise forms.ValidationError("Please upload a CSV file.")
        return upload
