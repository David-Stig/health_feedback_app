from django import forms

from facilities.models import Facility
from feedback.models import CollectionSession, ImportBatch
from feedback.forms import FeedbackForm

from .mixins import accessible_facilities_for_user


class CollectionSessionForm(forms.ModelForm):
    class Meta:
        model = CollectionSession
        fields = [
            "facility",
            "campaign_name",
            "start_date",
            "notes",
        ]
        labels = {
            "campaign_name": "Session name",
        }
        widgets = {
            "facility": forms.Select(attrs={"class": "form-control"}),
            "campaign_name": forms.TextInput(attrs={"class": "form-control"}),
            "start_date": forms.DateInput(attrs={"class": "form-control", "type": "date"}),
            "notes": forms.Textarea(attrs={"class": "form-control", "rows": 4}),
        }

    def __init__(self, *args, **kwargs):
        user = kwargs.pop("user")
        super().__init__(*args, **kwargs)
        self.fields["facility"].queryset = accessible_facilities_for_user(user)


class AssistedCaptureForm(FeedbackForm):
    pass


class ImportUploadForm(forms.ModelForm):
    class Meta:
        model = ImportBatch
        fields = ["stored_file", "facility", "collection_session"]
        widgets = {
            "stored_file": forms.FileInput(attrs={"class": "form-control"}),
            "facility": forms.Select(attrs={"class": "form-control"}),
            "collection_session": forms.Select(attrs={"class": "form-control"}),
        }

    def __init__(self, *args, **kwargs):
        user = kwargs.pop("user")
        super().__init__(*args, **kwargs)
        facility_queryset = accessible_facilities_for_user(user)
        self.fields["facility"].required = False
        self.fields["facility"].queryset = facility_queryset
        self.fields["collection_session"].required = False
        self.fields["collection_session"].queryset = CollectionSession.objects.filter(
            facility__in=facility_queryset,
        ).order_by("-created_at")

    def clean_stored_file(self):
        uploaded_file = self.cleaned_data["stored_file"]
        allowed_extensions = (".xlsx", ".csv")
        if not uploaded_file.name.lower().endswith(allowed_extensions):
            raise forms.ValidationError("Only .xlsx and .csv files are supported.")
        return uploaded_file
