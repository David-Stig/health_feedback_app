from django.conf import settings
from django.core.validators import MaxValueValidator, MinValueValidator
from django.db import models, transaction
from django.db.models import JSONField
from django.utils import timezone
from facilities.models import Facility


class SequenceCounter(models.Model):
    """Database-backed counter for human-readable bulk workflow codes."""

    scope = models.CharField(max_length=32)
    year = models.PositiveIntegerField()
    last_value = models.PositiveIntegerField(default=0)

    class Meta:
        unique_together = ("scope", "year")

    def __str__(self) -> str:
        return f"{self.scope}-{self.year}: {self.last_value}"


def next_sequence_code(scope: str, prefix: str) -> str:
    current_year = timezone.localdate().year
    with transaction.atomic():
        counter, _created = SequenceCounter.objects.select_for_update().get_or_create(
            scope=scope,
            year=current_year,
            defaults={"last_value": 0},
        )
        counter.last_value += 1
        counter.save(update_fields=["last_value"])
    return f"{prefix}-{current_year}-{counter.last_value:05d}"


class CollectionSession(models.Model):
    class Status(models.TextChoices):
        DRAFT = "draft", "Draft"
        ACTIVE = "active", "Active"
        PAUSED = "paused", "Paused"
        COMPLETED = "completed", "Completed"
        CANCELLED = "cancelled", "Cancelled"

    session_code = models.CharField(max_length=20, unique=True, editable=False, db_index=True)
    facility = models.ForeignKey(
        Facility,
        on_delete=models.CASCADE,
        related_name="collection_sessions",
    )
    campaign_name = models.CharField(max_length=255)
    programme_name = models.CharField(max_length=255, blank=True)
    collection_method = models.CharField(max_length=120, blank=True)
    collected_by = models.ForeignKey(
        settings.AUTH_USER_MODEL,
        on_delete=models.PROTECT,
        related_name="collection_sessions",
    )
    start_date = models.DateField(default=timezone.localdate)
    end_date = models.DateField(null=True, blank=True)
    location = models.CharField(max_length=255, blank=True)
    notes = models.TextField(blank=True)
    status = models.CharField(
        max_length=16,
        choices=Status.choices,
        default=Status.DRAFT,
        db_index=True,
    )
    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)

    class Meta:
        ordering = ["-created_at"]
        permissions = [
            ("complete_collectionsession", "Can complete collection session"),
            ("capture_assisted_feedback", "Can capture assisted feedback"),
        ]

    def __str__(self) -> str:
        return f"{self.session_code} - {self.facility.name}"

    @property
    def response_count(self) -> int:
        return self.feedback_entries.filter(is_active=True).count()

    def accepts_responses(self) -> bool:
        return self.status == self.Status.ACTIVE

    def save(self, *args, **kwargs):
        if not self.session_code:
            self.session_code = next_sequence_code("collection_session", "CS")
        super().save(*args, **kwargs)


class ImportBatch(models.Model):
    class Status(models.TextChoices):
        UPLOADED = "uploaded", "Uploaded"
        VALIDATING = "validating", "Validating"
        VALIDATION_FAILED = "validation_failed", "Validation failed"
        READY = "ready", "Ready"
        IMPORTING = "importing", "Importing"
        COMPLETED = "completed", "Completed"
        PARTIALLY_COMPLETED = "partially_completed", "Partially completed"
        ROLLED_BACK = "rolled_back", "Rolled back"
        FAILED = "failed", "Failed"

    batch_code = models.CharField(max_length=20, unique=True, editable=False, db_index=True)
    original_filename = models.CharField(max_length=255)
    stored_file = models.FileField(upload_to="bulk_imports/")
    uploaded_by = models.ForeignKey(
        settings.AUTH_USER_MODEL,
        on_delete=models.PROTECT,
        related_name="import_batches",
    )
    facility = models.ForeignKey(
        Facility,
        on_delete=models.SET_NULL,
        null=True,
        blank=True,
        related_name="import_batches",
    )
    collection_session = models.ForeignKey(
        CollectionSession,
        on_delete=models.SET_NULL,
        null=True,
        blank=True,
        related_name="import_batches",
    )
    total_rows = models.PositiveIntegerField(default=0)
    valid_rows = models.PositiveIntegerField(default=0)
    invalid_rows = models.PositiveIntegerField(default=0)
    imported_rows = models.PositiveIntegerField(default=0)
    duplicate_rows = models.PositiveIntegerField(default=0)
    status = models.CharField(
        max_length=24,
        choices=Status.choices,
        default=Status.UPLOADED,
        db_index=True,
    )
    validation_summary = JSONField(default=dict, blank=True)
    uploaded_at = models.DateTimeField(auto_now_add=True)
    completed_at = models.DateTimeField(null=True, blank=True)
    rolled_back_at = models.DateTimeField(null=True, blank=True)
    rolled_back_by = models.ForeignKey(
        settings.AUTH_USER_MODEL,
        on_delete=models.SET_NULL,
        null=True,
        blank=True,
        related_name="rolled_back_import_batches",
    )

    class Meta:
        ordering = ["-uploaded_at"]
        permissions = [
            ("validate_importbatch", "Can validate import batch"),
            ("confirm_importbatch", "Can confirm import batch"),
            ("rollback_importbatch", "Can roll back import batch"),
            ("download_import_errors", "Can download import errors"),
        ]

    def __str__(self) -> str:
        return f"{self.batch_code} - {self.original_filename}"

    def save(self, *args, **kwargs):
        if not self.batch_code:
            self.batch_code = next_sequence_code("import_batch", "IB")
        super().save(*args, **kwargs)


class BulkActionAuditLog(models.Model):
    event_type = models.CharField(max_length=64, db_index=True)
    actor = models.ForeignKey(
        settings.AUTH_USER_MODEL,
        on_delete=models.SET_NULL,
        null=True,
        blank=True,
        related_name="bulk_action_logs",
    )
    collection_session = models.ForeignKey(
        CollectionSession,
        on_delete=models.SET_NULL,
        null=True,
        blank=True,
        related_name="audit_logs",
    )
    import_batch = models.ForeignKey(
        ImportBatch,
        on_delete=models.SET_NULL,
        null=True,
        blank=True,
        related_name="audit_logs",
    )
    details = JSONField(default=dict, blank=True)
    created_at = models.DateTimeField(auto_now_add=True)

    class Meta:
        ordering = ["-created_at"]

    def __str__(self) -> str:
        return f"{self.event_type} @ {self.created_at:%Y-%m-%d %H:%M}"


class Feedback(models.Model):
    class SubmissionSource(models.TextChoices):
        QR_PUBLIC = "qr_public", "Public QR Submission"
        ASSISTED_CAPTURE = "assisted_capture", "Assisted Capture"
        SPREADSHEET_IMPORT = "spreadsheet_import", "Spreadsheet Import"

    class Category(models.TextChoices):
        WAITING_TIME = "Waiting time before being seen", "Waiting time before being seen"
        STAFF_ATTITUDE = "Respect and dignity from staff", "Respect and dignity from staff"
        CLEANLINESS = "Cleanliness of the health facility", "Cleanliness of the health facility"
        EXPLANATION = "Explanation of your illness and treatment", "Explanation of your illness and treatment"
        MEDICATION = "Availability of Medication", "Availability of Medication"
        
    #SECTION A: ABOUT YOUR VISIT 
    class AgeGroup(models.TextChoices):
        AGE_18_24 = "18-24 years", "18-24 years"
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
        NOT_NEEDED = "I have health insurance, but I did not need to use it", "I have health insurance, but I did not need to use it"
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
    submission_source = models.CharField(
        max_length=32,
        choices=SubmissionSource.choices,
        default=SubmissionSource.QR_PUBLIC,
        db_index=True,
    )
    collection_session = models.ForeignKey(
        CollectionSession,
        on_delete=models.SET_NULL,
        null=True,
        blank=True,
        related_name="feedback_entries",
    )
    import_batch = models.ForeignKey(
        ImportBatch,
        on_delete=models.SET_NULL,
        null=True,
        blank=True,
        related_name="feedback_entries",
    )
    captured_by = models.ForeignKey(
        settings.AUTH_USER_MODEL,
        on_delete=models.SET_NULL,
        null=True,
        blank=True,
        related_name="captured_feedback_entries",
    )
    submitted_on = models.DateField(null=True, blank=True, db_index=True)
    fingerprint = models.CharField(max_length=64, blank=True, db_index=True)
    consent_acknowledged = models.BooleanField(null=True, blank=True, default=None)
    consent_version = models.CharField(max_length=20, null=True, blank=True)
    is_active = models.BooleanField(default=True, db_index=True)
    rolled_back_at = models.DateTimeField(null=True, blank=True)
    rating = models.PositiveSmallIntegerField(
        validators=[MinValueValidator(1), MaxValueValidator(5)],
        null=True,
        blank=True,
    )
    category = models.CharField(max_length=64, choices=Category.choices, blank=True)
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
        return f"{self.facility.name} feedback #{self.pk}"

    @property
    def rating_response_count(self) -> int:
        if hasattr(self, "rating_response_total"):
            return self.rating_response_total
        return self.rating_responses.count()

    @property
    def average_rating_score(self):
        if hasattr(self, "average_rating_value"):
            return self.average_rating_value
        aggregate = self.rating_responses.aggregate(avg=models.Avg("rating"))
        return aggregate["avg"]

    def save(self, *args, **kwargs):
        if not self.submitted_on:
            self.submitted_on = timezone.localdate()
        super().save(*args, **kwargs)


class RatingResponse(models.Model):
    submission = models.ForeignKey(
        Feedback,
        on_delete=models.CASCADE,
        related_name="rating_responses",
    )
    category = models.CharField(max_length=64, choices=Feedback.Category.choices)
    rating = models.PositiveSmallIntegerField(validators=[MinValueValidator(1), MaxValueValidator(5)])
    comment = models.TextField(blank=True)
    created_at = models.DateTimeField(auto_now_add=True)

    class Meta:
        ordering = ["created_at", "pk"]
        constraints = [
            models.UniqueConstraint(
                fields=["submission", "category"],
                name="unique_rating_category_per_submission",
            ),
        ]
        indexes = [
            models.Index(fields=["submission", "category"]),
            models.Index(fields=["category"]),
        ]

    def __str__(self) -> str:
        return f"{self.submission_id} - {self.category} ({self.rating})"
