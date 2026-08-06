from django.contrib import admin

from intelligence.models import (
    IntelligenceConfiguration,
    IntelligenceInsight,
    IntelligenceReport,
    IntelligenceReportCounter,
    IntelligenceReportVersion,
)


@admin.register(IntelligenceConfiguration)
class IntelligenceConfigurationAdmin(admin.ModelAdmin):
    list_display = ("id", "stability_change_threshold", "significant_change_threshold", "updated_at")


class IntelligenceInsightInline(admin.TabularInline):
    model = IntelligenceInsight
    extra = 0
    fields = ("title", "insight_type", "severity", "direction", "confidence_level", "sample_size")
    readonly_fields = fields


class IntelligenceReportVersionInline(admin.TabularInline):
    model = IntelligenceReportVersion
    extra = 0
    fields = ("version", "generated_at", "generated_by")
    readonly_fields = fields


@admin.register(IntelligenceReport)
class IntelligenceReportAdmin(admin.ModelAdmin):
    list_display = ("report_code", "report_type", "title", "status", "version", "generated_at")
    list_filter = ("report_type", "status")
    search_fields = ("report_code", "title", "facility__name")
    inlines = [IntelligenceReportVersionInline, IntelligenceInsightInline]


@admin.register(IntelligenceInsight)
class IntelligenceInsightAdmin(admin.ModelAdmin):
    list_display = ("title", "report", "insight_type", "severity", "direction", "confidence_level")
    list_filter = ("insight_type", "severity", "direction", "confidence_level")
    search_fields = ("title", "summary", "metric_name")


@admin.register(IntelligenceReportCounter)
class IntelligenceReportCounterAdmin(admin.ModelAdmin):
    list_display = ("scope", "period_key", "last_value")
