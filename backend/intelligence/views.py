from __future__ import annotations

from django.contrib import messages
from django.db.models import Count
from django.http import FileResponse
from django.shortcuts import get_object_or_404, redirect
from django.urls import reverse_lazy
from django.utils import timezone
from django.views.generic import DetailView, FormView, ListView, TemplateView, UpdateView, View

from dashboard.mixins import StaffRequiredMixin
from feedback.models import Feedback
from intelligence.forms import (
    IntelligenceConfigurationForm,
    IntelligenceManagementCommentForm,
    IntelligenceReportGenerationForm,
)
from intelligence.models import IntelligenceConfiguration, IntelligenceInsight, IntelligenceReport
from intelligence.services.report_export_service import build_intelligence_report_pdf, report_pdf_filename
from intelligence.services.report_generation_service import generate_intelligence_report

RATING_LABEL_DEFINITIONS = {
    Feedback.Category.WAITING_TIME: {
        "short_label": "Waiting Time",
        "full_label": Feedback.Category.WAITING_TIME,
    },
    Feedback.Category.STAFF_ATTITUDE: {
        "short_label": "Respect & Dignity",
        "full_label": Feedback.Category.STAFF_ATTITUDE,
    },
    Feedback.Category.CLEANLINESS: {
        "short_label": "Cleanliness",
        "full_label": Feedback.Category.CLEANLINESS,
    },
    Feedback.Category.EXPLANATION: {
        "short_label": "Health Explanation",
        "full_label": Feedback.Category.EXPLANATION,
    },
    Feedback.Category.MEDICATION: {
        "short_label": "Medication",
        "full_label": Feedback.Category.MEDICATION,
    },
}

CHANGE_LABEL_DEFINITIONS = {
    Feedback.CHANGE.MORE_WORKERS: {
        "short_label": "Health workers",
        "full_label": Feedback.CHANGE.MORE_WORKERS,
    },
    Feedback.CHANGE.MORE_MEDICINES: {
        "short_label": "Medicines",
        "full_label": Feedback.CHANGE.MORE_MEDICINES,
    },
    Feedback.CHANGE.WAITING_TIME: {
        "short_label": "Waiting Time",
        "full_label": Feedback.CHANGE.WAITING_TIME,
    },
    Feedback.CHANGE.LOWER_COST: {
        "short_label": "Lower/No Costs",
        "full_label": Feedback.CHANGE.LOWER_COST,
    },
    Feedback.CHANGE.STAFF_ATTITUDE: {
        "short_label": "Staff Attitude",
        "full_label": Feedback.CHANGE.STAFF_ATTITUDE,
    },
    Feedback.CHANGE.OPENING_HOURS: {
        "short_label": "Operating Hours",
        "full_label": Feedback.CHANGE.OPENING_HOURS,
    },
    Feedback.CHANGE.OTHER: {
        "short_label": "Other",
        "full_label": Feedback.CHANGE.OTHER,
    },
}


class IntelligenceDashboardView(StaffRequiredMixin, TemplateView):
    template_name = "intelligence/dashboard.html"

    def get_context_data(self, **kwargs):
        context = super().get_context_data(**kwargs)
        recent_reports = IntelligenceReport.objects.select_related("facility").order_by("-generated_at")[:6]
        recent_insights = IntelligenceInsight.objects.select_related("report", "facility").filter(is_hidden=False)[:8]
        context.update(
            {
                "total_reports": IntelligenceReport.objects.count(),
                "draft_reports": IntelligenceReport.objects.filter(status=IntelligenceReport.Status.DRAFT).count(),
                "approved_reports": IntelligenceReport.objects.filter(status=IntelligenceReport.Status.APPROVED).count(),
                "recent_reports": recent_reports,
                "recent_insights": recent_insights,
                "configuration": IntelligenceConfiguration.load(),
            }
        )
        return context


class IntelligenceReportListView(StaffRequiredMixin, ListView):
    template_name = "intelligence/report_list.html"
    context_object_name = "reports"
    paginate_by = 10

    def get_queryset(self):
        queryset = IntelligenceReport.objects.select_related("facility", "generated_by", "approved_by")
        report_type = self.kwargs.get("report_type")
        if report_type:
            queryset = queryset.filter(report_type=report_type)
        return queryset.order_by("-generated_at", "-pk")

    def get_context_data(self, **kwargs):
        context = super().get_context_data(**kwargs)
        context["report_type"] = self.kwargs.get("report_type", "")
        context["report_type_label"] = dict(IntelligenceReport.ReportType.choices).get(
            self.kwargs.get("report_type", ""),
            "All reports",
        )
        return context


class IntelligenceReportGenerateView(StaffRequiredMixin, FormView):
    template_name = "intelligence/report_generate.html"
    form_class = IntelligenceReportGenerationForm
    success_url = reverse_lazy("intelligence:dashboard")

    def form_valid(self, form):
        report = generate_intelligence_report(
            user=self.request.user,
            report_type=form.cleaned_data["report_type"],
            facility=form.cleaned_data.get("facility"),
            collection_session=form.cleaned_data.get("collection_session"),
            submission_source=form.cleaned_data.get("submission_source", ""),
            period_start=form.cleaned_data.get("period_start"),
            period_end=form.cleaned_data.get("period_end"),
        )
        messages.success(self.request, f"Generated intelligence report {report.report_code}.")
        return redirect("intelligence:report_detail", pk=report.pk)


class IntelligenceReportDetailView(StaffRequiredMixin, DetailView):
    template_name = "intelligence/report_detail.html"
    context_object_name = "report"
    queryset = IntelligenceReport.objects.select_related(
        "facility",
        "generated_by",
        "reviewed_by",
        "approved_by",
    ).prefetch_related("versions", "insights")

    def get_context_data(self, **kwargs):
        context = super().get_context_data(**kwargs)
        report = self.object
        version = report.latest_version
        context["current_version"] = version
        context["insights"] = report.insights.filter(report_version=version, is_hidden=False) if version else []
        context["comment_form"] = IntelligenceManagementCommentForm(instance=report)
        context.update(
            {
                "report_rating_labels": [],
                "report_rating_full_labels": [],
                "report_rating_values": [],
                "report_change_labels": [],
                "report_change_full_labels": [],
                "report_change_values": [],
                "report_facility_labels": [],
                "report_facility_values": [],
                "report_topic_labels": [],
                "report_topic_values": [],
            }
        )
        if version:
            rating_insights = [
                item
                for item in version.insight_snapshot
                if item.get("metric_name") in dict(Feedback.Category.choices)
            ]
            structured_counts = version.supporting_statistics.get("structured_counts", {})
            facility_stats = version.supporting_statistics.get("facility_stats", [])
            topics = version.topic_snapshot or []
            rating_label_data = [RATING_LABEL_DEFINITIONS.get(item.get("metric_name"), {
                "short_label": item.get("metric_name"),
                "full_label": item.get("metric_name"),
            }) for item in rating_insights]
            change_rows = structured_counts.get("change", [])[:6]
            change_label_data = []
            for row in change_rows:
                raw_label = row.get("change") or row.get("received_service") or "Not provided"
                change_label_data.append(
                    CHANGE_LABEL_DEFINITIONS.get(
                        raw_label,
                        {"short_label": raw_label, "full_label": raw_label},
                    )
                )
            context.update(
                {
                    "report_rating_labels": [item["short_label"] for item in rating_label_data],
                    "report_rating_full_labels": [item["full_label"] for item in rating_label_data],
                    "report_rating_values": [float(item.get("current_value") or 0) for item in rating_insights],
                    "report_change_labels": [item["short_label"] for item in change_label_data],
                    "report_change_full_labels": [item["full_label"] for item in change_label_data],
                    "report_change_values": [row.get("total", 0) for row in change_rows],
                    "report_facility_labels": [row.get("facility__name") or "Unknown facility" for row in facility_stats[:6]],
                    "report_facility_values": [row.get("total", 0) for row in facility_stats[:6]],
                    "report_topic_labels": [row.get("topic", "") for row in topics[:6]],
                    "report_topic_values": [row.get("count", 0) for row in topics[:6]],
                }
            )
        return context

    def post(self, request, *args, **kwargs):
        self.object = self.get_object()
        form = IntelligenceManagementCommentForm(request.POST, instance=self.object)
        if form.is_valid():
            form.save()
            messages.success(request, "Management comments updated.")
            return redirect("intelligence:report_detail", pk=self.object.pk)
        context = self.get_context_data(comment_form=form)
        return self.render_to_response(context)


class IntelligenceReportStatusUpdateView(StaffRequiredMixin, View):
    def post(self, request, pk, action):
        report = get_object_or_404(IntelligenceReport, pk=pk)
        if action == "under-review":
            report.status = IntelligenceReport.Status.UNDER_REVIEW
            report.reviewed_by = request.user
            report.reviewed_at = timezone.now()
        elif action == "approve":
            report.status = IntelligenceReport.Status.APPROVED
            report.approved_by = request.user
            report.approved_at = timezone.now()
        elif action == "archive":
            report.status = IntelligenceReport.Status.ARCHIVED
        elif action == "cancel":
            report.status = IntelligenceReport.Status.CANCELLED
        else:
            messages.error(request, "Unknown report action.")
            return redirect("intelligence:report_detail", pk=report.pk)
        report.save(update_fields=["status", "reviewed_by", "reviewed_at", "approved_by", "approved_at", "updated_at"])
        messages.success(request, f"Report moved to {report.get_status_display().lower()}.")
        return redirect("intelligence:report_detail", pk=report.pk)


class IntelligenceReportRegenerateView(StaffRequiredMixin, View):
    def post(self, request, pk):
        report = get_object_or_404(IntelligenceReport, pk=pk)
        report = generate_intelligence_report(
            user=request.user,
            report_type=report.report_type,
            facility=report.facility,
            collection_session=report.collection_session,
            submission_source=report.submission_source,
            period_start=report.period_start,
            period_end=report.period_end,
            report=report,
        )
        messages.success(request, f"Regenerated {report.report_code} to version {report.version}.")
        return redirect("intelligence:report_detail", pk=report.pk)


class IntelligenceReportPdfDownloadView(StaffRequiredMixin, View):
    def get(self, request, pk):
        report = get_object_or_404(IntelligenceReport, pk=pk)
        pdf_buffer = build_intelligence_report_pdf(report)
        return FileResponse(
            pdf_buffer,
            as_attachment=True,
            filename=report_pdf_filename(report),
            content_type="application/pdf",
        )


class IntelligenceConfigurationView(StaffRequiredMixin, UpdateView):
    template_name = "intelligence/configuration.html"
    form_class = IntelligenceConfigurationForm
    success_url = reverse_lazy("intelligence:configuration")

    def get_object(self):
        return IntelligenceConfiguration.load()

    def form_valid(self, form):
        messages.success(self.request, "Intelligence configuration updated.")
        return super().form_valid(form)


class IntelligenceIssueListView(StaffRequiredMixin, TemplateView):
    template_name = "intelligence/issue_list.html"

    def get_context_data(self, **kwargs):
        context = super().get_context_data(**kwargs)
        insight_type = self.kwargs["insight_type"]
        insights = IntelligenceInsight.objects.select_related("report", "facility").filter(
            insight_type=insight_type,
            is_hidden=False,
        ).order_by("-created_at")[:50]
        context["insights"] = insights
        context["title"] = dict(IntelligenceInsight.InsightType.choices).get(insight_type, "Issues")
        return context


class IntelligenceTopicAnalysisView(StaffRequiredMixin, TemplateView):
    template_name = "intelligence/topic_analysis.html"

    def get_context_data(self, **kwargs):
        context = super().get_context_data(**kwargs)
        latest_versions = [report.latest_version for report in IntelligenceReport.objects.all()[:10]]
        topics = []
        for version in latest_versions:
            if version:
                topics.extend(version.topic_snapshot)
        topics = sorted(topics, key=lambda item: item.get("count", 0), reverse=True)[:20]
        context["topics"] = topics
        return context


class IntelligenceFacilityListView(StaffRequiredMixin, TemplateView):
    template_name = "intelligence/facility_intelligence.html"

    def get_context_data(self, **kwargs):
        context = super().get_context_data(**kwargs)
        facility_reports = (
            IntelligenceReport.objects.filter(report_type=IntelligenceReport.ReportType.FACILITY)
            .values("facility__name")
            .annotate(total=Count("id"))
            .order_by("-total", "facility__name")
        )
        context["facility_reports"] = facility_reports
        return context
