import csv
from io import TextIOWrapper
from datetime import timedelta

from django.contrib import messages
from django.contrib.admin.views.decorators import staff_member_required
from django.db import transaction
from django.db.models import Avg, Count
from django.db.models.functions import TruncDate
from django.http import HttpResponse
from django.urls import reverse_lazy
from django.utils import timezone
from django.views.generic import CreateView, DetailView, FormView, ListView, TemplateView, UpdateView

from facilities.forms import BulkFacilityUploadForm, FacilityForm
from facilities.models import Facility
from feedback.models import Feedback

from .forms import FeedbackFilterForm
from .mixins import StaffRequiredMixin


def filtered_feedback_queryset(params):
    queryset = Feedback.objects.select_related("facility").all()

    if params.get("province"):
        queryset = queryset.filter(facility__province=params["province"])
    if params.get("district"):
        queryset = queryset.filter(facility__district=params["district"])
    if params.get("facility"):
        queryset = queryset.filter(facility_id=params["facility"])
    if params.get("category"):
        queryset = queryset.filter(category=params["category"])
    if params.get("rating"):
        queryset = queryset.filter(rating=params["rating"])
    if params.get("date_from"):
        queryset = queryset.filter(created_at__date__gte=params["date_from"])
    if params.get("date_to"):
        queryset = queryset.filter(created_at__date__lte=params["date_to"])
    if params.get("search"):
        queryset = queryset.filter(comment__icontains=params["search"])

    return queryset


class DashboardHomeView(StaffRequiredMixin, TemplateView):
    template_name = "dashboard/home.html"

    def get_context_data(self, **kwargs):
        context = super().get_context_data(**kwargs)
        feedback_qs = Feedback.objects.select_related("facility")
        total_submissions = feedback_qs.count()
        recent_cutoff = timezone.now() - timedelta(days=30)

        trend_data = (
            feedback_qs.filter(created_at__gte=recent_cutoff)
            .annotate(day=TruncDate("created_at"))
            .values("day")
            .annotate(total=Count("id"), average_rating=Avg("rating"))
            .order_by("day")
        )

        category_breakdown = list(
            feedback_qs.values("category").annotate(total=Count("id")).order_by("-total")
        )
        facility_breakdown = list(
            feedback_qs.values("facility__name").annotate(total=Count("id")).order_by("-total")[:10]
        )
        province_breakdown = list(
            feedback_qs.values("facility__province").annotate(total=Count("id")).order_by("-total")
        ) 

        context.update(
            {
                "total_submissions": total_submissions,
                "facility_count": Facility.objects.count(),
                "average_rating": round(feedback_qs.aggregate(avg=Avg("rating"))["avg"] or 0, 2),
                "category_breakdown": category_breakdown,
                "facility_breakdown": facility_breakdown,
                "province_breakdown": province_breakdown,
                "trend_labels": [item["day"].strftime("%Y-%m-%d") for item in trend_data],
                "trend_totals": [item["total"] for item in trend_data],
                "trend_ratings": [round(item["average_rating"] or 0, 2) for item in trend_data],
                "category_labels": [item["category"] for item in category_breakdown],
                "category_totals": [item["total"] for item in category_breakdown],
            }
        )
        return context


class FeedbackListView(StaffRequiredMixin, ListView):
    template_name = "dashboard/feedback_list.html"
    model = Feedback
    paginate_by = 20
    context_object_name = "feedback_entries"

    def get_queryset(self):
        self.filter_form = FeedbackFilterForm(self.request.GET or None)
        if self.filter_form.is_valid():
            return filtered_feedback_queryset(self.filter_form.cleaned_data)
        return Feedback.objects.select_related("facility").all()

    def get_context_data(self, **kwargs):
        context = super().get_context_data(**kwargs)
        context["filter_form"] = self.filter_form
        return context


class FacilityListView(StaffRequiredMixin, ListView):
    template_name = "dashboard/facility_list.html"
    model = Facility
    context_object_name = "facilities"


class FacilityCreateView(StaffRequiredMixin, CreateView):
    template_name = "dashboard/facility_form.html"
    model = Facility
    form_class = FacilityForm
    success_url = reverse_lazy("dashboard:facility_list")

    def form_valid(self, form):
        messages.success(self.request, "Facility created successfully.")
        return super().form_valid(form)


class FacilityUpdateView(StaffRequiredMixin, UpdateView):
    template_name = "dashboard/facility_form.html"
    model = Facility
    form_class = FacilityForm
    success_url = reverse_lazy("dashboard:facility_list")

    def form_valid(self, form):
        messages.success(self.request, "Facility updated successfully.")
        return super().form_valid(form)


class FacilityDetailView(StaffRequiredMixin, DetailView):
    template_name = "dashboard/facility_detail.html"
    model = Facility
    context_object_name = "facility"


class FacilityBulkUploadView(StaffRequiredMixin, FormView):
    template_name = "dashboard/facility_bulk_upload.html"
    form_class = BulkFacilityUploadForm
    success_url = reverse_lazy("dashboard:facility_list")

    def form_valid(self, form):
        uploaded_file = form.cleaned_data["file"]
        decoded_file = TextIOWrapper(uploaded_file.file, encoding="utf-8-sig")
        reader = csv.DictReader(decoded_file)
        required_columns = {"name", "district", "province"}

        if not reader.fieldnames:
            form.add_error("file", "The uploaded CSV file is empty.")
            return self.form_invalid(form)

        normalized_columns = {column.strip().lower() for column in reader.fieldnames if column}
        if not required_columns.issubset(normalized_columns):
            form.add_error("file", "CSV must include the columns: name, district, province.")
            return self.form_invalid(form)

        created_count = 0
        skipped_count = 0
        invalid_rows = []

        with transaction.atomic():
            for index, row in enumerate(reader, start=2):
                normalized_row = {
                    (key or "").strip().lower(): (value or "").strip()
                    for key, value in row.items()
                }
                name = normalized_row.get("name", "")
                district = normalized_row.get("district", "")
                province = normalized_row.get("province", "")

                if not name or not district or not province:
                    invalid_rows.append(index)
                    continue

                facility, created = Facility.objects.get_or_create(
                    name=name,
                    district=district,
                    province=province,
                )
                if created:
                    created_count += 1
                else:
                    skipped_count += 1

        if invalid_rows:
            messages.warning(
                self.request,
                f"Upload completed with skipped rows: {', '.join(str(row) for row in invalid_rows)}.",
            )

        messages.success(
            self.request,
            f"Bulk upload finished. Created {created_count} facilities and skipped {skipped_count} duplicates.",
        )
        return super().form_valid(form)


@staff_member_required
def export_feedback_csv(request):
    queryset = filtered_feedback_queryset(request.GET).select_related("facility")
    response = HttpResponse(content_type="text/csv")
    response["Content-Disposition"] = 'attachment; filename="feedback-export.csv"'

    writer = csv.writer(response)
    writer.writerow(["Date", "Facility", "District", "Province", "Rating", "Category", "Comment"])

    for entry in queryset:
        writer.writerow(
            [
                entry.created_at.strftime("%Y-%m-%d %H:%M"),
                entry.facility.name,
                entry.facility.district,
                entry.facility.province,
                entry.rating,
                entry.category,
                entry.comment,
            ]
        )

    return response


@staff_member_required
def export_feedback_excel(request):
    from openpyxl import Workbook

    queryset = filtered_feedback_queryset(request.GET).select_related("facility")
    workbook = Workbook()
    sheet = workbook.active
    sheet.title = "Feedback"
    sheet.append(["Date", "Facility", "District", "Province", "Rating", "Category", "Comment"])

    for entry in queryset:
        sheet.append(
            [
                entry.created_at.strftime("%Y-%m-%d %H:%M"),
                entry.facility.name,
                entry.facility.district,
                entry.facility.province,
                entry.rating,
                entry.category,
                entry.comment,
            ]
        )

    response = HttpResponse(
        content_type="application/vnd.openxmlformats-officedocument.spreadsheetml.sheet"
    )
    response["Content-Disposition"] = 'attachment; filename="feedback-export.xlsx"'
    workbook.save(response)
    return response
