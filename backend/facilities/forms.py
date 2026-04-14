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
