from django.core.validators import MaxValueValidator, MinValueValidator
from django.db import models
from facilities.models import Facility


class Feedback(models.Model):
    class Category(models.TextChoices):
        WAITING_TIME = "Waiting Time", "Waiting Time"
        STAFF_ATTITUDE = "Staff Attitude", "Staff Attitude"
        PRIVACY = "Privacy", "Privacy"
        SERVICE_QUALITY = "Service Quality", "Service Quality"
        MEDICATION = "Availability of Medication", "Availability of Medication"
        CLEANLINESS = "Cleanliness", "Cleanliness"
        YOUTH_FRIENDLY = "Youth Friendly Services", "Youth Friendly Services"

    class AgeGroup(models.TextChoices):
        UNDER_18 = "Under 18", "Under 18"
        AGE_18_24 = "18-24", "18-24"
        AGE_25_34 = "25-34", "25-34"
        AGE_35_44 = "35-44", "35-44"
        AGE_45_54 = "45-54", "45-54"
        AGE_55_PLUS = "55+", "55+"

    class Gender(models.TextChoices):
        FEMALE = "Female", "Female"
        MALE = "Male", "Male"
        

    facility = models.ForeignKey(Facility, on_delete=models.CASCADE, related_name="feedback_entries")
    rating = models.PositiveSmallIntegerField(validators=[MinValueValidator(1), MaxValueValidator(5)])
    category = models.CharField(max_length=64, choices=Category.choices)
    comment = models.TextField(blank=True)
    age_group = models.CharField(max_length=20, choices=AgeGroup.choices, blank=True)
    gender = models.CharField(max_length=24, choices=Gender.choices, blank=True)
    created_at = models.DateTimeField(auto_now_add=True)

    class Meta:
        ordering = ["-created_at"]

    def __str__(self) -> str:
        return f"{self.facility.name} - {self.category} ({self.rating})"
