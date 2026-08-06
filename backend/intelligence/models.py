from __future__ import annotations

from django.conf import settings
from django.db import models, transaction
from django.utils import timezone

from dashboard.models import DashboardUserProfile
from facilities.models import Facility
from feedback.models import CollectionSession


class IntelligenceReportCounter(models.Model):
    scope = models.CharField(max_length=32)
    period_key = models.CharField(max_length=32)
    last_value = models.PositiveIntegerField(default=0)

    class Meta:
        unique_together = ("scope", "period_key")


class IntelligenceConfiguration(models.Model):
    stability_change_threshold = models.DecimalField(max_digits=5, decimal_places=2, default=5)
    significant_change_threshold = models.DecimalField(max_digits=5, decimal_places=2, default=15)
    sudden_spike_percentage = models.DecimalField(max_digits=5, decimal_places=2, default=30)
    sudden_spike_minimum_count = models.PositiveIntegerField(default=5)
    minimum_sample_insufficient = models.PositiveIntegerField(default=4)
    minimum_sample_low_volume = models.PositiveIntegerField(default=19)
    low_rating_threshold = models.DecimalField(max_digits=3, decimal_places=2, default=2.5)
    minimum_recurring_periods = models.PositiveIntegerField(default=2)
    minimum_cross_facility_count = models.PositiveIntegerField(default=2)
    updated_at = models.DateTimeField(auto_now=True)

    def __str__(self) -> str:
        return "Operational intelligence configuration"

    @classmethod
    def load(cls) -> "IntelligenceConfiguration":
        config, _created = cls.objects.get_or_create(pk=1)
        return config


class IntelligenceReport(models.Model):
    class ReportType(models.TextChoices):
        WEEKLY = "weekly", "Weekly"
        MONTHLY = "monthly", "Monthly"
        CUSTOM = "custom", "Custom Period"
        FACILITY = "facility", "Facility"

    class Status(models.TextChoices):
        DRAFT = "draft", "Draft"
        UNDER_REVIEW = "under_review", "Under Review"
        APPROVED = "approved", "Approved"
        ARCHIVED = "archived", "Archived"
        CANCELLED = "cancelled", "Cancelled"

    report_code = models.CharField(max_length=32, unique=True, editable=False, db_index=True)
    report_type = models.CharField(max_length=16, choices=ReportType.choices, db_index=True)
    title = models.CharField(max_length=255)
    facility = models.ForeignKey(
        Facility,
        on_delete=models.SET_NULL,
        null=True,
        blank=True,
        related_name="intelligence_reports",
    )
    collection_session = models.ForeignKey(
        CollectionSession,
        on_delete=models.SET_NULL,
        null=True,
        blank=True,
        related_name="intelligence_reports",
    )
    submission_source = models.CharField(max_length=32, blank=True)
    period_start = models.DateField()
    period_end = models.DateField()
    comparison_start = models.DateField(null=True, blank=True)
    comparison_end = models.DateField(null=True, blank=True)
    status = models.CharField(max_length=16, choices=Status.choices, default=Status.DRAFT, db_index=True)
    version = models.PositiveIntegerField(default=1)
    generated_at = models.DateTimeField(default=timezone.now)
    generated_by = models.ForeignKey(
        settings.AUTH_USER_MODEL,
        on_delete=models.SET_NULL,
        null=True,
        blank=True,
        related_name="generated_intelligence_reports",
    )
    reviewed_by = models.ForeignKey(
        settings.AUTH_USER_MODEL,
        on_delete=models.SET_NULL,
        null=True,
        blank=True,
        related_name="reviewed_intelligence_reports",
    )
    reviewed_at = models.DateTimeField(null=True, blank=True)
    approved_by = models.ForeignKey(
        settings.AUTH_USER_MODEL,
        on_delete=models.SET_NULL,
        null=True,
        blank=True,
        related_name="approved_intelligence_reports",
    )
    approved_at = models.DateTimeField(null=True, blank=True)
    executive_summary = models.TextField(blank=True)
    management_comments = models.TextField(blank=True)
    generation_metadata = models.JSONField(default=dict, blank=True)
    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)

    class Meta:
        ordering = ["-generated_at", "-created_at"]
        permissions = [
            ("review_intelligencereport", "Can review intelligence report"),
            ("approve_intelligencereport", "Can approve intelligence report"),
            ("regenerate_intelligencereport", "Can regenerate intelligence report"),
        ]

    def __str__(self) -> str:
        return self.title

    @property
    def latest_version(self) -> "IntelligenceReportVersion | None":
        return self.versions.order_by("-version").first()

    def save(self, *args, **kwargs):
        if not self.report_code:
            self.report_code = generate_report_code(self.report_type, self.period_start, self.period_end)
        super().save(*args, **kwargs)


class IntelligenceReportVersion(models.Model):
    report = models.ForeignKey(
        IntelligenceReport,
        on_delete=models.CASCADE,
        related_name="versions",
    )
    version = models.PositiveIntegerField()
    executive_summary = models.TextField(blank=True)
    recommendations = models.JSONField(default=list, blank=True)
    supporting_statistics = models.JSONField(default=dict, blank=True)
    insight_snapshot = models.JSONField(default=list, blank=True)
    topic_snapshot = models.JSONField(default=list, blank=True)
    generation_settings = models.JSONField(default=dict, blank=True)
    generated_at = models.DateTimeField(default=timezone.now)
    generated_by = models.ForeignKey(
        settings.AUTH_USER_MODEL,
        on_delete=models.SET_NULL,
        null=True,
        blank=True,
        related_name="generated_intelligence_report_versions",
    )

    class Meta:
        ordering = ["-version"]
        constraints = [
            models.UniqueConstraint(fields=["report", "version"], name="unique_intelligence_report_version"),
        ]

    def __str__(self) -> str:
        return f"{self.report.report_code} v{self.version}"


class IntelligenceInsight(models.Model):
    class InsightType(models.TextChoices):
        METRIC = "metric", "Metric"
        TREND = "trend", "Trend"
        EMERGING_ISSUE = "emerging_issue", "Emerging issue"
        RECURRING_ISSUE = "recurring_issue", "Recurring issue"
        POSITIVE_DEVELOPMENT = "positive_development", "Positive development"
        FACILITY_ALERT = "facility_alert", "Facility alert"
        TOPIC = "topic", "Topic"

    class Severity(models.TextChoices):
        CRITICAL = "critical", "Critical"
        HIGH = "high", "High"
        MEDIUM = "medium", "Medium"
        LOW = "low", "Low"
        INFORMATIONAL = "informational", "Informational"

    class Direction(models.TextChoices):
        IMPROVING = "improving", "Improving"
        DECLINING = "declining", "Declining"
        STABLE = "stable", "Stable"
        SUDDEN_SPIKE = "sudden_spike", "Sudden spike"
        INSUFFICIENT_DATA = "insufficient_data", "Insufficient data"

    class ConfidenceLevel(models.TextChoices):
        HIGH = "high", "High"
        MEDIUM = "medium", "Medium"
        LOW = "low", "Low"
        INSUFFICIENT = "insufficient", "Insufficient"

    report = models.ForeignKey(
        IntelligenceReport,
        on_delete=models.CASCADE,
        related_name="insights",
    )
    report_version = models.ForeignKey(
        IntelligenceReportVersion,
        on_delete=models.CASCADE,
        related_name="insights",
    )
    facility = models.ForeignKey(
        Facility,
        on_delete=models.SET_NULL,
        null=True,
        blank=True,
        related_name="intelligence_insights",
    )
    insight_type = models.CharField(max_length=32, choices=InsightType.choices)
    title = models.CharField(max_length=255)
    summary = models.TextField()
    severity = models.CharField(max_length=16, choices=Severity.choices, default=Severity.INFORMATIONAL)
    direction = models.CharField(max_length=24, choices=Direction.choices, default=Direction.STABLE)
    confidence_level = models.CharField(
        max_length=16,
        choices=ConfidenceLevel.choices,
        default=ConfidenceLevel.INSUFFICIENT,
    )
    confidence_score = models.DecimalField(max_digits=5, decimal_places=2, default=0)
    metric_name = models.CharField(max_length=255, blank=True)
    current_value = models.DecimalField(max_digits=12, decimal_places=2, null=True, blank=True)
    comparison_value = models.DecimalField(max_digits=12, decimal_places=2, null=True, blank=True)
    absolute_change = models.DecimalField(max_digits=12, decimal_places=2, null=True, blank=True)
    percentage_change = models.DecimalField(max_digits=8, decimal_places=2, null=True, blank=True)
    sample_size = models.PositiveIntegerField(default=0)
    evidence = models.JSONField(default=dict, blank=True)
    display_order = models.PositiveIntegerField(default=0)
    is_hidden = models.BooleanField(default=False)
    reviewer_notes = models.TextField(blank=True)
    created_at = models.DateTimeField(auto_now_add=True)

    class Meta:
        ordering = ["display_order", "pk"]

    def __str__(self) -> str:
        return self.title


def generate_report_code(report_type: str, period_start, period_end) -> str:
    if report_type == IntelligenceReport.ReportType.WEEKLY:
        iso_year, iso_week, _weekday = period_start.isocalendar()
        scope = "wir"
        prefix = "WIR"
        period_key = f"{iso_year}-W{iso_week:02d}"
        label = f"{iso_year}-W{iso_week:02d}"
    elif report_type == IntelligenceReport.ReportType.MONTHLY:
        scope = "mir"
        prefix = "MIR"
        period_key = f"{period_start.year}-{period_start.month:02d}"
        label = period_key
    elif report_type == IntelligenceReport.ReportType.FACILITY:
        scope = "fir"
        prefix = "FIR"
        period_key = f"{period_start:%Y%m%d}-{period_end:%Y%m%d}"
        label = f"{period_start:%Y%m%d}"
    else:
        scope = "cir"
        prefix = "CIR"
        period_key = f"{period_start:%Y%m%d}-{period_end:%Y%m%d}"
        label = f"{period_start:%Y%m%d}"

    with transaction.atomic():
        counter, _created = IntelligenceReportCounter.objects.select_for_update().get_or_create(
            scope=scope,
            period_key=period_key,
            defaults={"last_value": 0},
        )
        counter.last_value += 1
        counter.save(update_fields=["last_value"])
    return f"{prefix}-{label}-{counter.last_value:04d}"
