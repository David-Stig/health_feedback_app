from django import forms
from facilities.models import Facility
from .models import Feedback


class FeedbackForm(forms.ModelForm):
    honeypot = forms.CharField(required=False, widget=forms.HiddenInput)
    difficulty = forms.MultipleChoiceField(
        choices=Feedback.Difficulty.choices,
        widget=forms.CheckboxSelectMultiple(attrs={"class": "form-check"}),
        required=False,
        help_text="Select all that apply"
    )

    class Meta:
        model = Feedback
        fields = ["facility", "comment", "age_group", "gender", "change", "aob", "aob_other", "reason_not_chance", "reason_not_chance_other", 
                  "chance", "revisit", "medicines", "cost", "cash_payment", "cash_payment_other", "no_insurance_reason", "insurance", "payment", 
                  "referral", "received_service", "difficulty", "service", "service_other", "distance", "reason_not_received", 
                  "reason_not_received_other", "no_insurance_reason_other", "change_other", "facility_type", "facility_type_other"]
        widgets = {
            "facility": forms.Select(attrs={"class": "form-control"}), 
            "comment": forms.Textarea(
                attrs={
                    "class": "form-control",
                    "rows": 4,
                    "placeholder": "Optional comment",
                }
            ),
            "age_group": forms.Select(attrs={"class": "form-control"}), 
            "gender": forms.Select(attrs={"class": "form-control"}),    
            "change": forms.Select(attrs={"class": "form-control"}),
            "change_other": forms.Textarea(attrs={"class": "form-control", "rows": 3, "placeholder": "Please specify..."}),
            "aob": forms.Select(attrs={"class": "form-control"}),
            "aob_other": forms.Textarea(attrs={"class": "form-control", "rows": 3, "placeholder": "Please specify..."}),
            "reason_not_chance": forms.Select(attrs={"class": "form-control"}),
            "reason_not_chance_other": forms.Textarea(attrs={"class": "form-control", "rows": 3, "placeholder": "Please specify..."}),
            "chance": forms.Select(attrs={"class": "form-control"}),
            "revisit": forms.Select(attrs={"class": "form-control"}),
            "medicines": forms.Select(attrs={"class": "form-control"}),
            "cost": forms.Select(attrs={"class": "form-control"}),
            "cash_payment": forms.Select(attrs={"class": "form-control"}),  
            "cash_payment_other": forms.Textarea(attrs={"class": "form-control", "rows": 3, "placeholder": "Please specify..."}),
            "no_insurance_reason": forms.Select(attrs={"class": "form-control"}),
            "insurance": forms.Select(attrs={"class": "form-control"}),
            "insurance_other": forms.Textarea(attrs={"class": "form-control", "rows": 3, "placeholder": "Please specify..."}),
            "no_insurance_reason_other": forms.Textarea(attrs={"class": "form-control", "rows": 3, "placeholder": "Please specify..."}),
            "payment": forms.Select(attrs={"class": "form-control"}),
            "referral": forms.Select(attrs={"class": "form-control"}),
            "facility_type": forms.Select(attrs={"class": "form-control"}),
            "facility_type_other": forms.Textarea(attrs={"class": "form-control", "rows": 3, "placeholder": "Please specify..."}),
            "received_service": forms.Select(attrs={"class": "form-control"}),
            "service": forms.Select(attrs={"class": "form-control"}),
            "service_other": forms.Textarea(attrs={"class": "form-control", "rows": 3, "placeholder": "Please specify..."}),
            "distance": forms.Select(attrs={"class": "form-control"}),
            "reason_not_received": forms.Select(attrs={"class": "form-control"}),
            "reason_not_received_other": forms.Textarea(attrs={"class": "form-control", "rows": 3, "placeholder": "Please specify..."}),
            "facility_type_other": forms.Textarea(attrs={"class": "form-control", "rows": 3, "placeholder": "Please specify..."}),
        }

    def __init__(self, *args, **kwargs):
        facility_id = kwargs.pop("facility_id", None)
        super().__init__(*args, **kwargs)

        if facility_id:
            self.fields["facility"].queryset = Facility.objects.filter(pk=facility_id)
            self.fields["facility"].initial = facility_id
        else:
            self.fields["facility"].queryset = Facility.objects.all()
        self.fields["age_group"].required = True
        self.fields["gender"].required = True
        self.fields["comment"].required = False
        self.fields["facility"].empty_label = None
        self.fields["distance"].required = True
        self.fields["change"].required = True
        self.fields["change_other"].required = False
        self.fields["aob"].required = True
        self.fields["aob_other"].required = False
        self.fields["reason_not_chance"].required = False
        self.fields["reason_not_chance_other"].required = False
        self.fields["chance"].required = True
        self.fields["revisit"].required = True
        self.fields["medicines"].required = True
        self.fields["cost"].required = True
        self.fields["cash_payment"].required = False
        self.fields["cash_payment_other"].required = False
        self.fields["insurance"].required = True
        self.fields["no_insurance_reason"].required = False
        self.fields["no_insurance_reason_other"].required = False
        self.fields["payment"].required = True
        self.fields["referral"].required = True
        self.fields["facility_type"].required = False
        self.fields["facility_type_other"].required = False
        self.fields["received_service"].required = True
        self.fields["difficulty"].required = True
        self.fields["service"].required = True
        self.fields["service_other"].required = False
        self.fields["reason_not_received"].required = False
        self.fields["reason_not_received_other"].required = False

    def clean_honeypot(self):
        value = self.cleaned_data.get("honeypot")
        if value:
            raise forms.ValidationError("Spam detected.")
        return value

    def clean_difficulty(self):
        # Ensure difficulty is stored as a list
        difficulty = self.cleaned_data.get("difficulty")
        if isinstance(difficulty, str):
            return [difficulty] if difficulty else []
        return difficulty or []

    def clean(self):
        cleaned_data = super().clean()
        service_other = cleaned_data.get("service_other")
        reason_not_received_other = cleaned_data.get("reason_not_received_other")
        reason_not_chance_other = cleaned_data.get("reason_not_chance_other")
        aob_other = cleaned_data.get("aob_other")
        change_other = cleaned_data.get("change_other")
        cash_payment_other = cleaned_data.get("cash_payment_other")
        no_insurance_reason_other = cleaned_data.get("no_insurance_reason_other")
        facility_type_other = cleaned_data.get("facility_type_other")
        
        # Conditional required field validation
        # service='Other' -> service_other required
        if cleaned_data.get("service") == Feedback.Service.OTHER:
            if not service_other:
                self.add_error("service_other", "Please specify the service.")
        
        # reason_not_received='Other' -> reason_not_received_other required
        if cleaned_data.get("reason_not_received") == Feedback.ReasonNotReceived.OTHER:
            if not reason_not_received_other:
                self.add_error("reason_not_received_other", "Please specify the reason.")
        
        # reason_not_chance='Other' -> reason_not_chance_other required
        if cleaned_data.get("reason_not_chance") == Feedback.REASON_NOT_CHANCE.OTHER:
            if not reason_not_chance_other:
                self.add_error("reason_not_chance_other", "Please specify.")
        
        # aob='Yes' -> aob_other required
        if cleaned_data.get("aob") == Feedback.AOB.YES:
            if not aob_other:
                self.add_error("aob_other", "Please specify.")
        
        # change='Other' -> change_other required
        if cleaned_data.get("change") == Feedback.CHANGE.OTHER:
            if not change_other:
                self.add_error("change_other", "Please specify the change.")
        
        # received_service is not 'Yes' -> reason_not_received required
        if cleaned_data.get("received_service") != Feedback.receivedService.YES:
            if not cleaned_data.get("reason_not_received"):
                self.add_error("reason_not_received", "Please explain why you didn't receive all services.")
        
        # cash_payment='Other' -> cash_payment_other required
        if cleaned_data.get("cash_payment") == Feedback.CASH.OTHER:
            if not cash_payment_other:
                self.add_error("cash_payment_other", "Please specify the amount.")
        
        # no_insurance_reason='Other' -> no_insurance_reason_other required
        if cleaned_data.get("no_insurance_reason") == Feedback.NO_INSURANCE_REASON.OTHER:
            if not no_insurance_reason_other:
                self.add_error("no_insurance_reason_other", "Please specify the reason.")
        
        # facility_type='Other' -> facility_type_other required
        if cleaned_data.get("facility_type") == Feedback.FacilityType.OTHER:
            if not facility_type_other:
                self.add_error("facility_type_other", "Please specify the facility type.")
        
        if cleaned_data.get("service") != Feedback.Service.OTHER:
            cleaned_data["service_other"] = ""
        if cleaned_data.get("reason_not_received") != Feedback.ReasonNotReceived.OTHER:
            cleaned_data["reason_not_received_other"] = ""
        if cleaned_data.get("reason_not_chance") != Feedback.REASON_NOT_CHANCE.OTHER:
            cleaned_data["reason_not_chance_other"] = ""
        if cleaned_data.get("aob") != Feedback.AOB.YES:
            cleaned_data["aob_other"] = ""
        if cleaned_data.get("change") != Feedback.CHANGE.OTHER:
            cleaned_data["change_other"] = ""
        if cleaned_data.get("cash_payment") != Feedback.CASH.OTHER:
            cleaned_data["cash_payment_other"] = ""
        if cleaned_data.get("no_insurance_reason") != Feedback.NO_INSURANCE_REASON.OTHER:
            cleaned_data["no_insurance_reason_other"] = ""
        if cleaned_data.get("facility_type") != Feedback.FacilityType.OTHER:
            cleaned_data["facility_type_other"] = ""

        return cleaned_data
