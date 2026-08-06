from django import forms
from django.utils import timezone

from facilities.models import Facility
from feedback.models import CollectionSession, Feedback
from intelligence.models import IntelligenceConfiguration, IntelligenceReport


class IntelligenceReportGenerationForm(forms.Form):
    report_type = forms.ChoiceField(choices=IntelligenceReport.ReportType.choices)
    facility = forms.ModelChoiceField(queryset=Facility.objects.all(), required=False)
    collection_session = forms.ModelChoiceField(queryset=CollectionSession.objects.all(), required=False)
    submission_source = forms.ChoiceField(
        choices=[("", "All submission sources"), *Feedback.SubmissionSource.choices],
        required=False,
    )
    period_start = forms.DateField(
        required=False,
        initial=lambda: timezone.localdate(),
        widget=forms.DateInput(attrs={"type": "date"}),
    )
    period_end = forms.DateField(
        required=False,
        initial=lambda: timezone.localdate(),
        widget=forms.DateInput(attrs={"type": "date"}),
    )

    def clean(self):
        cleaned_data = super().clean()
        report_type = cleaned_data.get("report_type")
        facility = cleaned_data.get("facility")
        period_start = cleaned_data.get("period_start")
        period_end = cleaned_data.get("period_end")

        if report_type == IntelligenceReport.ReportType.FACILITY and not facility:
            self.add_error("facility", "Facility intelligence reports require a selected facility.")
        if report_type == IntelligenceReport.ReportType.CUSTOM:
            if not period_start or not period_end:
                raise forms.ValidationError("Custom reports require both a start and end date.")
            if period_end < period_start:
                raise forms.ValidationError("End date cannot be earlier than start date.")
        return cleaned_data


class IntelligenceConfigurationForm(forms.ModelForm):
    class Meta:
        model = IntelligenceConfiguration
        fields = [
            "stability_change_threshold",
            "significant_change_threshold",
            "sudden_spike_percentage",
            "sudden_spike_minimum_count",
            "minimum_sample_insufficient",
            "minimum_sample_low_volume",
            "low_rating_threshold",
            "minimum_recurring_periods",
            "minimum_cross_facility_count",
        ]


class IntelligenceManagementCommentForm(forms.ModelForm):
    class Meta:
        model = IntelligenceReport
        fields = ["management_comments"]
        widgets = {
            "management_comments": forms.Textarea(attrs={"rows": 4}),
        }
