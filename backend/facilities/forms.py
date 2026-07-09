from django import forms

from .models import Facility

ZAMBIA_PROVINCES_AND_DISTRICTS = {
    "Central": [
        "Chibombo",
        "Chisamba",
        "Itezhi-Tezhi",
        "Kabwe",
        "Kapiri Mposhi",
        "Luano",
        "Mkushi",
        "Mumbwa",
        "Ngabwe",
        "Serenje",
        "Shibuyunji",
    ],
    "Copperbelt": [
        "Chililabombwe",
        "Chingola",
        "Kalulushi",
        "Kitwe",
        "Luanshya",
        "Lufwanyama",
        "Masaiti",
        "Mpongwe",
        "Mufulira",
        "Ndola",
    ],
    "Eastern": [
        "Chadiza",
        "Chasefu",
        "Chipangali",
        "Chipata",
        "Kasenengwa",
        "Katete",
        "Lumezi",
        "Lundazi",
        "Mambwe",
        "Nyimba",
        "Petauke",
        "Sinda",
        "Vubwi",
    ],
    "Luapula": [
        "Chembe",
        "Chiengi",
        "Chipili",
        "Kawambwa",
        "Lunga",
        "Mansa",
        "Milenge",
        "Mwansabombwe",
        "Mwense",
        "Nchelenge",
        "Samfya",
    ],
    "Lusaka": [
        "Chilanga",
        "Chongwe",
        "Kafue",
        "Luangwa",
        "Lusaka",
        "Rufunsa",
        "Shibuyunji",
    ],
    "Muchinga": [
        "Chama",
        "Chinsali",
        "Isoka",
        "Kanchibiya",
        "Lavushimanda",
        "Mafinga",
        "Mpika",
        "Nakonde",
        "Shiwang'andu",
    ],
    "Northern": [
        "Chilubi",
        "Kaputa",
        "Kasama",
        "Lunte",
        "Lupososhi",
        "Luwingu",
        "Mbala",
        "Mporokoso",
        "Mpulungu",
        "Mungwi",
        "Nsama",
        "Senga Hill",
    ],
    "North-Western": [
        "Chavuma",
        "Ikelenge",
        "Kabompo",
        "Kalumbila",
        "Kasempa",
        "Manyinga",
        "Mufumbwe",
        "Mushindamo",
        "Mwinilunga",
        "Solwezi",
        "Zambezi",
    ],
    "Southern": [
        "Chikankata",
        "Chirundu",
        "Choma",
        "Gwembe",
        "Kalomo",
        "Kazungula",
        "Livingstone",
        "Mazabuka",
        "Monze",
        "Namwala",
        "Pemba",
        "Siavonga",
        "Sinazongwe",
        "Zimba",
    ],
    "Western": [
        "Kalabo",
        "Kaoma",
        "Limulunga",
        "Luampa",
        "Lukulu",
        "Mitete",
        "Mongu",
        "Mulobezi",
        "Mwandi",
        "Nalolo",
        "Nkeyema",
        "Senanga",
        "Sesheke",
        "Shang'ombo",
        "Sikongo",
        "Sioma",
    ],
}


def province_choices():
    return [("", "Select province")] + [
        (province, province) for province in sorted(ZAMBIA_PROVINCES_AND_DISTRICTS)
    ]


def district_choices(province=None):
    districts = ZAMBIA_PROVINCES_AND_DISTRICTS.get(province, [])
    return [("", "Select district")] + [(district, district) for district in districts]


class FacilityForm(forms.ModelForm):
    province = forms.ChoiceField(
        choices=province_choices(),
        widget=forms.Select(attrs={"class": "form-control"}),
    )
    district = forms.ChoiceField(
        choices=district_choices(),
        widget=forms.Select(attrs={"class": "form-control"}),
    )

    class Meta:
        model = Facility
        fields = ["name", "district", "province"]
        widgets = {
            "name": forms.TextInput(attrs={"class": "form-control", "placeholder": "Facility name"}),
        }

    def __init__(self, *args, **kwargs):
        super().__init__(*args, **kwargs)
        province = None
        if self.is_bound:
            province = self.data.get("province")
        elif self.instance.pk:
            province = self.instance.province
        elif self.initial.get("province"):
            province = self.initial["province"]
        self.fields["district"].choices = district_choices(province)

    def clean(self):
        cleaned_data = super().clean()
        province = cleaned_data.get("province")
        district = cleaned_data.get("district")

        if province and district:
            valid_districts = ZAMBIA_PROVINCES_AND_DISTRICTS.get(province, [])
            if district not in valid_districts:
                self.add_error("district", "Selected district does not belong to the chosen province.")

        return cleaned_data


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
