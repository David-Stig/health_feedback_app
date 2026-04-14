from django import forms

from facilities.models import Facility

from .models import Feedback


class FeedbackForm(forms.ModelForm):
    honeypot = forms.CharField(required=False, widget=forms.HiddenInput)

    class Meta:
        model = Feedback
        fields = ["facility", "rating", "category", "comment", "age_group", "gender"]
        widgets = {
            "facility": forms.Select(attrs={"class": "form-control"}),
            "rating": forms.RadioSelect(choices=[(value, "★" * value) for value in range(1, 6)]),
            "category": forms.Select(attrs={"class": "form-control"}),
            "comment": forms.Textarea(attrs={"class": "form-control", "rows": 4, "placeholder": "Optional comment"}),
            "age_group": forms.Select(attrs={"class": "form-control"}),
            "gender": forms.Select(attrs={"class": "form-control"}),
        }

    def __init__(self, *args, **kwargs):
        facility_id = kwargs.pop("facility_id", None)
        super().__init__(*args, **kwargs)
        self.fields["facility"].queryset = Facility.objects.all()
        self.fields["age_group"].required = False
        self.fields["gender"].required = False
        self.fields["comment"].required = False
        self.fields["facility"].empty_label = None
        if facility_id:
            self.fields["facility"].initial = facility_id

    def clean_rating(self):
        rating = self.cleaned_data["rating"]
        if rating < 1 or rating > 5:
            raise forms.ValidationError("Rating must be between 1 and 5.")
        return rating

    def clean_honeypot(self):
        value = self.cleaned_data["honeypot"]
        if value:
            raise forms.ValidationError("Spam detected.")
        return value
