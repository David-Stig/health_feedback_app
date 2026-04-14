from django import forms

from facilities.models import Facility
from feedback.models import Feedback


class FeedbackFilterForm(forms.Form):
    province = forms.ChoiceField(required=False)
    district = forms.ChoiceField(required=False)
    facility = forms.ModelChoiceField(queryset=Facility.objects.all(), required=False)
    category = forms.ChoiceField(required=False)
    rating = forms.ChoiceField(required=False)
    date_from = forms.DateField(required=False, widget=forms.DateInput(attrs={"type": "date"}))
    date_to = forms.DateField(required=False, widget=forms.DateInput(attrs={"type": "date"}))
    search = forms.CharField(required=False)

    def __init__(self, *args, **kwargs):
        super().__init__(*args, **kwargs)
        provinces = Facility.objects.values_list("province", flat=True).distinct().order_by("province")
        districts = Facility.objects.values_list("district", flat=True).distinct().order_by("district")
        self.fields["province"].choices = [("", "All provinces")] + [(p, p) for p in provinces]
        self.fields["district"].choices = [("", "All districts")] + [(d, d) for d in districts]
        self.fields["category"].choices = [("", "All categories")] + list(Feedback.Category.choices)
        self.fields["rating"].choices = [("", "All ratings")] + [(str(i), str(i)) for i in range(1, 6)]

        for field in self.fields.values():
            css_class = "form-control"
            if isinstance(field.widget, forms.DateInput):
                field.widget.attrs["class"] = css_class
            else:
                field.widget.attrs.update({"class": css_class})
