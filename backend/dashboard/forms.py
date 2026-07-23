from django import forms
from django.contrib.auth import get_user_model
from django.contrib.auth.forms import PasswordChangeForm, SetPasswordForm, UserCreationForm

from facilities.models import Facility
from feedback.models import Feedback

from .models import get_or_create_dashboard_profile

User = get_user_model()


class FeedbackFilterForm(forms.Form):
    province = forms.ChoiceField(required=False)
    district = forms.ChoiceField(required=False)
    facility = forms.ModelChoiceField(queryset=Facility.objects.all(), required=False)
    category = forms.ChoiceField(required=False) 
    gender = forms.ChoiceField(required=False)
    rating = forms.ChoiceField(required=False)
    submission_source = forms.ChoiceField(required=False)
    collection_session = forms.ModelChoiceField(queryset=Feedback.collection_session.field.related_model.objects.all(), required=False)
    date_from = forms.DateField(required=False, widget=forms.DateInput(attrs={"type": "date"}))
    date_to = forms.DateField(required=False, widget=forms.DateInput(attrs={"type": "date"}))
    search = forms.CharField(required=False)
    # distance = forms.ChoiceField(required=False, choices=[("", "All distances")] + list(Feedback.Distance.choices))

    def __init__(self, *args, **kwargs):
        super().__init__(*args, **kwargs)
        provinces = Facility.objects.values_list("province", flat=True).distinct().order_by("province")
        districts = Facility.objects.values_list("district", flat=True).distinct().order_by("district")
        self.fields["province"].choices = [("", "All provinces")] + [(p, p) for p in provinces]
        self.fields["district"].choices = [("", "All districts")] + [(d, d) for d in districts]
        self.fields["category"].choices = [("", "All categories")] + list(Feedback.Category.choices)
        self.fields["gender"].choices = [("", "All genders")] + list(Feedback.Gender.choices)
        self.fields["rating"].choices = [("", "All ratings")] + [(str(i), str(i)) for i in range(1, 6)]
        submission_source_choices = [
            choice
            for choice in Feedback.SubmissionSource.choices
            if choice[0] != Feedback.SubmissionSource.SPREADSHEET_IMPORT
        ]
        self.fields["submission_source"].choices = [("", "All submission sources")] + submission_source_choices
        self.fields["collection_session"].queryset = Feedback.collection_session.field.related_model.objects.order_by("-created_at")

        for field in self.fields.values():
            css_class = "form-control"
            if isinstance(field.widget, forms.DateInput):
                field.widget.attrs["class"] = css_class
            else:
                field.widget.attrs.update({"class": css_class})


class DashboardUserCreationForm(UserCreationForm):
    first_name = forms.CharField(required=False, widget=forms.TextInput(attrs={"class": "form-control"}))
    last_name = forms.CharField(required=False, widget=forms.TextInput(attrs={"class": "form-control"}))
    email = forms.EmailField(required=False, widget=forms.EmailInput(attrs={"class": "form-control"}))
    is_dashboard_user = forms.BooleanField(required=False, initial=True)
    facility = forms.ModelChoiceField(
        queryset=Facility.objects.all(),
        required=False,
        widget=forms.Select(attrs={"class": "form-control"}), 
    )

    class Meta(UserCreationForm.Meta):
        model = User
        fields = (
            "username",
            "first_name",
            "last_name",
            "email",
            "password1",
            "password2",
            "is_dashboard_user",
            "facility",
        )

    def __init__(self, *args, **kwargs):
        super().__init__(*args, **kwargs)
        self.fields["username"].widget.attrs.update({"class": "form-control"})
        self.fields["password1"].widget.attrs.update({"class": "form-control"})
        self.fields["password2"].widget.attrs.update({"class": "form-control"})

    def save(self, commit=True):
        user = super().save(commit=False)
        user.first_name = self.cleaned_data.get("first_name", "")
        user.last_name = self.cleaned_data.get("last_name", "")
        user.email = self.cleaned_data.get("email", "")
        if commit:
            user.save()
            profile = get_or_create_dashboard_profile(user)
            profile.is_dashboard_user = self.cleaned_data["is_dashboard_user"]
            profile.facility = self.cleaned_data.get("facility")
            profile.save()
        return user


class DashboardUserUpdateForm(forms.ModelForm):
    first_name = forms.CharField(required=False, widget=forms.TextInput(attrs={"class": "form-control"}))
    last_name = forms.CharField(required=False, widget=forms.TextInput(attrs={"class": "form-control"}))
    email = forms.EmailField(required=False, widget=forms.EmailInput(attrs={"class": "form-control"}))
    is_dashboard_user = forms.BooleanField(required=False)
    facility = forms.ModelChoiceField(
        queryset=Facility.objects.all(),
        required=False,
        widget=forms.Select(attrs={"class": "form-control"}),
    )

    class Meta:
        model = User
        fields = ("username", "first_name", "last_name", "email", "is_dashboard_user", "facility")

    def __init__(self, *args, **kwargs):
        super().__init__(*args, **kwargs)
        self.fields["username"].widget.attrs.update({"class": "form-control"})
        profile = get_or_create_dashboard_profile(self.instance)
        self.fields["is_dashboard_user"].initial = profile.is_dashboard_user
        self.fields["facility"].initial = profile.facility

    def save(self, commit=True):
        user = super().save(commit=False)
        if commit:
            user.save()
            profile = get_or_create_dashboard_profile(user)
            profile.is_dashboard_user = self.cleaned_data["is_dashboard_user"]
            profile.facility = self.cleaned_data.get("facility")
            profile.save()
        return user


class DashboardUserPasswordResetForm(SetPasswordForm):
    def __init__(self, user, *args, **kwargs):
        super().__init__(user, *args, **kwargs)
        self.fields["new_password1"].widget.attrs.update({"class": "form-control"})
        self.fields["new_password2"].widget.attrs.update({"class": "form-control"})


class DashboardAccountForm(forms.ModelForm):
    username = forms.CharField(widget=forms.TextInput(attrs={"class": "form-control"}))
    email = forms.EmailField(required=False, widget=forms.EmailInput(attrs={"class": "form-control"}))

    class Meta:
        model = User
        fields = ("username", "first_name", "last_name", "email")

    def __init__(self, *args, **kwargs):
        super().__init__(*args, **kwargs)
        self.fields["first_name"].widget.attrs.update({"class": "form-control"})
        self.fields["last_name"].widget.attrs.update({"class": "form-control"})


class DashboardPasswordChangeForm(PasswordChangeForm):
    def __init__(self, user, *args, **kwargs):
        super().__init__(user, *args, **kwargs)
        self.fields["old_password"].widget.attrs.update({"class": "form-control"})
        self.fields["new_password1"].widget.attrs.update({"class": "form-control"})
        self.fields["new_password2"].widget.attrs.update({"class": "form-control"})
