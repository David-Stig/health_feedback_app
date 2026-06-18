from django.core.validators import MaxValueValidator, MinValueValidator
from django.db import models
from django.db.models import JSONField
from facilities.models import Facility


class Feedback(models.Model):
    class Category(models.TextChoices):
        WAITING_TIME = "Waiting time before being seen", "Waiting time before being seen"
        STAFF_ATTITUDE = "Respect and dignity from staff", "Respect and dignity from staff"
        CLEANLINESS = "Cleanliness of the health facility", "Cleanliness of the health facility"
        EXPLANATION = "Explanation of your illness and treatment", "Explanation of your illness and treatment"
        MEDICATION = "Availability of Medication", "Availability of Medication"
        
    #SECTION A: ABOUT YOUR VISIT 
    class AgeGroup(models.TextChoices):
        AGE_15_24 = "15-24 years", "15-24 years"
        AGE_25_34 = "25-34 years", "25-34 years"
        AGE_35_49 = "35-49 years", "35-49 years"
        AGE_50_64 = "50-64 years", "50-64 years"
        AGE_65_PLUS = "65+ years", "65+ years"

    class Gender(models.TextChoices):
        FEMALE = "Female", "Female"
        MALE = "Male", "Male"
        PREFER_NOT_TO_SAY = "Prefer not to say", "Prefer not to say"

    class Distance(models.TextChoices):
        LESS_THAN_5KM = "Less than 5 km", "Less than 5 km"
        BETWEEN_5KM_AND_10KM = "Between 5 km and 10 km", "Between 5 km and 10 km"
        MORE_THAN_10KM = "More than 10 km", "More than 10 km"

    class Service(models.TextChoices):
        TREATMENT = "Treatment for illness/injury", "Treatment for illness/injury"
        CHILDREN = "Child health: immunization or sick child", "Child health: immunization or sick child"
        MATERNAL = "Maternal health: antenatal, postnatal, family planning", "Maternal health: antenatal, postnatal, family planning"
        CHRONIC = "Chronic disease care: hypertension, diabetes, HIV, TB", "Chronic disease care: hypertension, diabetes, HIV, TB"
        LABORATORY = "Laboratory test or scan only", "Laboratory test or scan only"
        PHARMACY = "To collect medicines only", "To collect medicines only"
        MULTIPLE = "Multiple reasons", "Multiple reasons"
        OTHER = "Other", "Other"

    class Difficulty(models.TextChoices):
        SEEING = "Seeing (even with glasses)", "Seeing (even with glasses)"
        HEARING = "Hearing (even with hearing aid)", "Hearing (even with hearing aid)"
        MOBILITY = "Walking or climbing steps", "Walking or climbing steps"
        REMEMBERING = " Remembering or concentrating", " Remembering or concentrating"
        SELF_CARE = "Self-care (washing, dressing)", "Self-care (washing, dressing)"
        COMMUNICATING = "Communicating", "Communicating"
        NONE = " No difficulty", " No difficulty"

    # SECTION B: SERVICE COVERAGE
    class receivedService(models.TextChoices):
        YES = "Yes, I received everything I needed", "Yes, I received everything I needed"
        NO = "No, I did not receive what I needed", "No, I did not receive what I needed"
        PARTIALLY = "Partially, I received some but not all", "Partially, I received some but not all"

    class ReasonNotReceived(models.TextChoices):
        NOT_AVAILABLE = "Health worker was not available", "Health worker was not available"
        MEDICINE = "Medicines were out of stock", "Medicines were out of stock"
        EQUIPMENT = "Laboratory test or equipment not available", "Laboratory test or equipment not available"
        RETURN = "I was asked to return another day", "I was asked to return another day"
        REFERRAL = "I was referred to another facility", "I was referred to another facility"
        OTHER = "Other", "Other"

    class Referral(models.TextChoices):
        YES = "Yes", "Yes"
        NO = "No", "No"

    class FacilityType(models.TextChoices):
        HOSPITAL = "Hospital", "Hospital"
        BIGGER_CLINIC = "Bigger Clinic", "Bigger Clinic"
        OTHER = "Other", "Other"

    # SCETION C: FINAL COMMENTS
    class Payment(models.TextChoices):
        YES = "Yes", "Yes"
        NO = "No", "No"

    class INSURANCE(models.TextChoices):
        NHIMA = "NHIMA (National Health Insurance)", "NHIMA (National Health Insurance)"
        PRIVATE = "Private Insurance", "Private Insurance"
        BOTH = "Both NHIMA and private", "Both NHIMA and private"
        NONE = "None", "None"
        NOT_SURE = "Not sure", "Not sure"

    class NO_INSURANCE_REASON(models.TextChoices):
        NONE = "I do not have any health insurance", "I do not have any health insurance"
        FORGOT = "I have NHIMA, but I forgot my card / number", "I have NHIMA, but I forgot my card / number"
        PRIVATE = "I have private insurance, but I forgot my card / number", "I have private insurance, but I forgot my card / number"
        FACILITY = "I have NHIMA, but the facility did not accept it", "I have NHIMA, but the facility did not accept it"
        PRIVATE_FACILITY = "I have private insurance, but this health post does not accept it ", "I have private insurance, but this health post does not accept it "
        DID_NOT_HAVE = "My insurance does not cover the services I needed today", "My insurance does not cover the services I needed today"
        CASH = "I chose to pay out-of-pocket instead", "I chose to pay out-of-pocket instead"
        NOT_SURE = "Not sure", "Not sure"
        OTHER = "Other", "Other"

    class CASH(models.TextChoices):
        LESS = "Less than K20", "Less than K20"
        BETWEEN = "Between K20 and K50", "Between K20 and K50"
        BETWEEN_50_100 = "Between K50 and K100", "Between K50 and K100"
        MORE = "More than K100", "More than K100"
        DONT_REMEMBER = "I don't remember", "I don't remember"
        OTHER = "other", "other"

    class COST(models.TextChoices):
        YES = "Yes", "Yes"
        NO = "No", "No"
        NA = "Not Applicable", "Not Applicable"
        NOT_SURE = "Not sure", "Not sure"

    # SECTION D: Quality

    class MEDICINES(models.TextChoices):
        YES = "Yes, got all medicines here", "Yes, got all medicines here"
        NO_PHARMACY = "No, told to buy some at a pharmacy", "No, told to buy some at a pharmacy"
        NO = "No, did not get the medicines at all", "No, did not get the medicines at all"
        NO_PRESCRIPTION = "No medicines were prescribed", "No medicines were prescribed"

    class REVISIT(models.TextChoices):
        YES = "Yes", "Yes"
        NO = "No", "No"
        NOT_SURE = "Not sure", "Not sure"

    # SECTION E: UHC 

    class CHANCE(models.TextChoices):
        YES = "Yes", "Yes"
        NO = "No", "No"
        DONT_KNOW = "Don't know", "Don't know"

    class REASON_NOT_CHANCE(models.TextChoices):
        POOR = "Very poor people", "Very poor people"
        FAR = "People who live far away", "People who live far away"
        WOMEN = "Women", "Women"
        ELDERLY = "Elderly people", "Elderly people"
        DISABILITIES = "People with disabilities", "People with disabilities"
        OTHER = "Other", "Other"

    class CHANGE(models.TextChoices):
        MORE_WORKERS = "More health workers available", "More health workers available"
        MORE_MEDICINES = "More medicines in stock", "More medicines in stock"
        WAITING_TIME = "Shorter waiting time", "Shorter waiting time"
        LOWER_COST = "Lower costs / no fees", "Lower costs / no fees"
        STAFF_ATTITUDE = "Better staff attitude", "Better staff attitude"
        OPENING_HOURS = "Longer opening hours", "Longer opening hours"
        OTHER = "Other", "Other"

    class AOB(models.TextChoices):
        YES = "Yes", "Yes"
        NO = "No", "No"

      

    facility = models.ForeignKey(Facility, on_delete=models.CASCADE, related_name="feedback_entries")
    rating = models.PositiveSmallIntegerField(validators=[MinValueValidator(1), MaxValueValidator(5)])
    category = models.CharField(max_length=64, choices=Category.choices)
    comment = models.TextField(blank=True)
    age_group = models.CharField(max_length=20, choices=AgeGroup.choices, blank=True)
    gender = models.CharField(max_length=24, choices=Gender.choices, blank=True)
    distance = models.CharField(max_length=32, choices=Distance.choices, blank=True)
    service = models.CharField(max_length=64, choices=Service.choices, blank=True)
    difficulty = JSONField(default=list, blank=True, help_text="Select all that apply")
    received_service = models.CharField(max_length=64, choices=receivedService.choices, blank=True)
    reason_not_received = models.CharField(max_length=64, choices=ReasonNotReceived.choices, blank=True)
    referral = models.CharField(max_length=32, choices=Referral.choices, blank=True)
    facility_type = models.CharField(max_length=32, choices=FacilityType.choices, blank=True)
    facility_type_other = models.TextField(blank=True, help_text="Specify if 'Other' is selected for facility_type")
    payment = models.CharField(max_length=32, choices=Payment.choices, blank=True)
    insurance = models.CharField(max_length=64, choices=INSURANCE.choices, blank=True)
    no_insurance_reason = models.CharField(max_length=128, choices=NO_INSURANCE_REASON.choices, blank=True)
    no_insurance_reason_other = models.TextField(blank=True, help_text="Specify if 'Other' is selected for no_insurance_reason")
    cash_payment = models.CharField(max_length=32, choices=CASH.choices, blank=True)
    cash_payment_other = models.TextField(blank=True, help_text="Specify if 'Other' is selected for cash_payment")
    cost = models.CharField(max_length=32, choices=COST.choices, blank=True)
    medicines = models.CharField(max_length=64, choices=MEDICINES.choices, blank=True)
    revisit = models.CharField(max_length=32, choices=REVISIT.choices, blank=True)
    chance = models.CharField(max_length=32, choices=CHANCE.choices, blank=True)
    reason_not_chance = models.CharField(max_length=64, choices=REASON_NOT_CHANCE.choices, blank=True)
    reason_not_chance_other = models.TextField(blank=True, help_text="Specify if 'Other' is selected for reason_not_chance")
    change = models.CharField(max_length=64, choices=CHANGE.choices, blank=True)
    change_other = models.TextField(blank=True, help_text="Specify if 'Other' is selected for change")
    aob = models.CharField(max_length=32, choices=AOB.choices, blank=True)
    aob_other = models.TextField(blank=True, help_text="Specify if 'Other' is selected for AOB")
    service_other = models.TextField(blank=True, help_text="Specify if 'Other' is selected for service")
    reason_not_received_other = models.TextField(blank=True, help_text="Specify if 'Other' is selected for reason_not_received")
    created_at = models.DateTimeField(auto_now_add=True)

    class Meta:
        ordering = ["-created_at"]

    def __str__(self) -> str:
        return f"{self.facility.name} - {self.category} ({self.rating})"