import csv
from io import TextIOWrapper
from datetime import timedelta

from django.contrib import messages
from django.contrib.auth import get_user_model
from django.contrib.auth import update_session_auth_hash
from django.contrib.auth.views import redirect_to_login
from django.db import transaction
from django.db.models import Avg, Count, Q
from django.db.models.functions import TruncDate
from django.http import HttpResponse
from django.shortcuts import get_object_or_404, redirect
from django.urls import reverse_lazy
from django.utils import timezone
from django.views.generic import CreateView, DeleteView, DetailView, FormView, ListView, TemplateView, UpdateView

from facilities.forms import BulkFacilityUploadForm, FacilityForm, ZAMBIA_PROVINCES_AND_DISTRICTS
from facilities.models import Facility
from feedback.models import Feedback

from .forms import (
    DashboardAccountForm,
    DashboardPasswordChangeForm,
    DashboardUserCreationForm,
    DashboardUserUpdateForm,
    DashboardUserPasswordResetForm,
    FeedbackFilterForm,
)
from .mixins import DashboardAccessMixin, StaffRequiredMixin
from .models import get_or_create_dashboard_profile

User = get_user_model()

EXPORT_COLUMNS = [
    ("Date", lambda entry: entry.created_at.strftime("%Y-%m-%d %H:%M")),
    ("Submitted on", lambda entry: entry.submitted_on.strftime("%Y-%m-%d") if entry.submitted_on else ""),
    ("Facility", lambda entry: entry.facility.name),
    ("District", lambda entry: entry.facility.district),
    ("Province", lambda entry: entry.facility.province),
    ("Submission source", lambda entry: entry.get_submission_source_display()),
    ("Collection session", lambda entry: entry.collection_session.session_code if entry.collection_session_id else ""),
    ("Rating", lambda entry: entry.rating),
    ("Category", lambda entry: entry.category),
    ("Comment", lambda entry: entry.comment),
    ("Age group", lambda entry: entry.age_group),
    ("Gender", lambda entry: entry.gender),
    ("Distance", lambda entry: entry.distance),
    ("Service", lambda entry: entry.service),
    ("Service other", lambda entry: entry.service_other),
    (
        "Difficulty",
        lambda entry: ", ".join(entry.difficulty) if isinstance(entry.difficulty, list) else entry.difficulty,
    ),
    ("Received service", lambda entry: entry.received_service),
    ("Reason not received", lambda entry: entry.reason_not_received),
    ("Reason not received other", lambda entry: entry.reason_not_received_other),
    ("Referral", lambda entry: entry.referral),
    ("Facility type", lambda entry: entry.facility_type),
    ("Facility type other", lambda entry: entry.facility_type_other),
    ("Payment", lambda entry: entry.payment),
    ("Insurance", lambda entry: entry.insurance),
    ("No insurance reason", lambda entry: entry.no_insurance_reason),
    ("No insurance reason other", lambda entry: entry.no_insurance_reason_other),
    ("Cash payment", lambda entry: entry.cash_payment),
    ("Cash payment other", lambda entry: entry.cash_payment_other),
    ("Cost impact", lambda entry: entry.cost),
    ("Medicines", lambda entry: entry.medicines),
    ("Revisit", lambda entry: entry.revisit),
    ("Chance", lambda entry: entry.chance),
    ("Reason not chance", lambda entry: entry.reason_not_chance),
    ("Reason not chance other", lambda entry: entry.reason_not_chance_other),
    ("Change", lambda entry: entry.change),
    ("Change other", lambda entry: entry.change_other),
    ("Anything else", lambda entry: entry.aob),
    ("Anything else detail", lambda entry: entry.aob_other),
]


def export_row(entry):
    return [getter(entry) for _label, getter in EXPORT_COLUMNS]


def choice_breakdown(queryset, field_name, choices, *, include_blank=False):
    choice_map = dict(choices)
    breakdown = list(
        queryset.values(field_name).annotate(total=Count("id")).order_by("-total")
    )

    items = []
    for item in breakdown:
        raw_value = item[field_name]
        if not raw_value and not include_blank:
            continue
        label = choice_map.get(raw_value, raw_value or "Not provided")
        items.append({"value": raw_value, "label": label, "total": item["total"]})
    return items


def display_choice(instance, field_name):
    value = getattr(instance, field_name)
    if not value:
        return "Not provided"
    display_method = getattr(instance, f"get_{field_name}_display", None)
    return display_method() if callable(display_method) else value


def display_text(value, default="Not provided"):
    if value is None:
        return default
    if isinstance(value, str):
        return value.strip() or default
    return value


def display_choice_list(values, choices):
    if not values:
        return "Not provided"
    choice_map = dict(choices)
    return ", ".join(choice_map.get(value, value) for value in values)


def scoped_feedback_queryset(user):
    queryset = Feedback.objects.select_related("facility", "collection_session", "import_batch", "captured_by").filter(is_active=True)
    if user.is_authenticated and not user.is_staff:
        profile = get_or_create_dashboard_profile(user)
        if profile.is_dashboard_user and profile.facility_id:
            queryset = queryset.filter(facility_id=profile.facility_id)
    return queryset


def filtered_feedback_queryset(user, params):
    queryset = scoped_feedback_queryset(user)

    if params.get("province"):
        queryset = queryset.filter(facility__province=params["province"]) 
    if params.get("district"):
        queryset = queryset.filter(facility__district=params["district"])
    if params.get("facility"):
        queryset = queryset.filter(facility_id=params["facility"])
    if params.get("gender"):
        queryset = queryset.filter(gender=params["gender"])
    if params.get("category"):
        queryset = queryset.filter(category=params["category"])
    if params.get("rating"):
        queryset = queryset.filter(rating=params["rating"])
    if params.get("submission_source"):
        queryset = queryset.filter(submission_source=params["submission_source"])
    if params.get("collection_session"):
        queryset = queryset.filter(collection_session=params["collection_session"])
    if params.get("distance"):
        queryset = queryset.filter(distance=params["distance"])
    if params.get("date_from"):
        queryset = queryset.filter(created_at__date__gte=params["date_from"])
    if params.get("date_to"):
        queryset = queryset.filter(created_at__date__lte=params["date_to"])
    if params.get("search"):
        queryset = queryset.filter(comment__icontains=params["search"])

    return queryset


class DashboardHomeView(DashboardAccessMixin, TemplateView):
    template_name = "dashboard/home.html"

    def get_context_data(self, **kwargs):
        context = super().get_context_data(**kwargs)
        feedback_qs = scoped_feedback_queryset(self.request.user)
        total_submissions = feedback_qs.count()
        recent_cutoff = timezone.now() - timedelta(days=30)
        source_breakdown = choice_breakdown(
            feedback_qs,
            "submission_source",
            Feedback.SubmissionSource.choices,
        )


        trend_data = (
            feedback_qs.filter(created_at__gte=recent_cutoff)
            .annotate(day=TruncDate("created_at"))
            .values("day")
            .annotate(total=Count("id"), average_rating=Avg("rating"))
            .order_by("day")
        )

        gender_breakdown = list(
            feedback_qs.values("gender").annotate(total=Count("id")).order_by("-total")
        )
        distance_breakdown = list(
            feedback_qs.values("distance").annotate(total=Count("id")).order_by("-total")
        )
        category_breakdown = list(
            feedback_qs.values("category").annotate(total=Count("id")).order_by("-total")
        )
        received_service_breakdown = choice_breakdown(
            feedback_qs,
            "received_service",
            Feedback.receivedService.choices,
        )
        payment_breakdown = choice_breakdown(
            feedback_qs,
            "payment",
            Feedback.Payment.choices,
        )
        medicines_breakdown = choice_breakdown(
            feedback_qs,
            "medicines",
            Feedback.MEDICINES.choices,
        )
        revisit_breakdown = choice_breakdown(
            feedback_qs,
            "revisit",
            Feedback.REVISIT.choices,
        )
        insurance_breakdown = choice_breakdown(
            feedback_qs,
            "insurance",
            Feedback.INSURANCE.choices,
        )
        change_breakdown = choice_breakdown(
            feedback_qs,
            "change",
            Feedback.CHANGE.choices,
        )
        reason_not_received_breakdown = choice_breakdown(
            feedback_qs,
            "reason_not_received",
            Feedback.ReasonNotReceived.choices,
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
                "gender_breakdown": gender_breakdown,
                "category_breakdown": category_breakdown,
                "source_breakdown": source_breakdown,
                "received_service_breakdown": received_service_breakdown,
                "payment_breakdown": payment_breakdown,
                "medicines_breakdown": medicines_breakdown,
                "revisit_breakdown": revisit_breakdown,
                "insurance_breakdown": insurance_breakdown,
                "change_breakdown": change_breakdown,
                "reason_not_received_breakdown": reason_not_received_breakdown,
                "facility_breakdown": facility_breakdown,
                "province_breakdown": province_breakdown,
                "trend_labels": [item["day"].strftime("%Y-%m-%d") for item in trend_data],
                "trend_totals": [item["total"] for item in trend_data],
                "trend_ratings": [round(item["average_rating"] or 0, 2) for item in trend_data],
                "gender_labels": [item["gender"] for item in gender_breakdown],
                "gender_totals": [item["total"] for item in gender_breakdown],
                "category_labels": [item["category"] for item in category_breakdown],
                "category_totals": [item["total"] for item in category_breakdown],
                "source_labels": [item["label"] for item in source_breakdown],
                "source_totals": [item["total"] for item in source_breakdown],
                "received_service_labels": [item["label"] for item in received_service_breakdown],
                "received_service_totals": [item["total"] for item in received_service_breakdown],
                "payment_labels": [item["label"] for item in payment_breakdown],
                "payment_totals": [item["total"] for item in payment_breakdown],
                "medicines_labels": [item["label"] for item in medicines_breakdown],
                "medicines_totals": [item["total"] for item in medicines_breakdown],
                "revisit_labels": [item["label"] for item in revisit_breakdown],
                "revisit_totals": [item["total"] for item in revisit_breakdown],
                "insurance_labels": [item["label"] for item in insurance_breakdown],
                "insurance_totals": [item["total"] for item in insurance_breakdown],
                "change_labels": [item["label"] for item in change_breakdown],
                "change_totals": [item["total"] for item in change_breakdown],
                "public_qr_total": feedback_qs.filter(submission_source=Feedback.SubmissionSource.QR_PUBLIC).count(),
                "assisted_total": feedback_qs.filter(submission_source=Feedback.SubmissionSource.ASSISTED_CAPTURE).count(),
                "imported_total": feedback_qs.filter(submission_source=Feedback.SubmissionSource.SPREADSHEET_IMPORT).count(),
                "active_session_total": Feedback.collection_session.field.related_model.objects.filter(status="active").count(),
                "completed_import_total": Feedback.import_batch.field.related_model.objects.filter(status__in=["completed", "partially_completed"]).count(),
                "rejected_import_row_total": sum(
                    Feedback.import_batch.field.related_model.objects.values_list("invalid_rows", flat=True)
                ),
            }
        )
        return context


class DashboardAccountView(DashboardAccessMixin, TemplateView):
    template_name = "dashboard/account.html"

    def get_context_data(self, **kwargs):
        context = super().get_context_data(**kwargs)
        context.setdefault("profile_form", DashboardAccountForm(instance=self.request.user))
        context.setdefault("password_form", DashboardPasswordChangeForm(self.request.user))
        return context

    def post(self, request, *args, **kwargs):
        action = request.POST.get("account_action")

        if action == "profile":
            profile_form = DashboardAccountForm(request.POST, instance=request.user)
            password_form = DashboardPasswordChangeForm(request.user)
            if profile_form.is_valid():
                profile_form.save()
                messages.success(request, "Profile details updated successfully.")
                return redirect("dashboard:account")
        elif action == "password":
            profile_form = DashboardAccountForm(instance=request.user)
            password_form = DashboardPasswordChangeForm(request.user, request.POST)
            if password_form.is_valid():
                user = password_form.save()
                update_session_auth_hash(request, user)
                messages.success(request, "Password changed successfully.")
                return redirect("dashboard:account")
        else:
            profile_form = DashboardAccountForm(instance=request.user)
            password_form = DashboardPasswordChangeForm(request.user)
            messages.error(request, "Unable to process that account update.")

        context = self.get_context_data(
            profile_form=profile_form,
            password_form=password_form,
        )
        return self.render_to_response(context)


class FeedbackListView(DashboardAccessMixin, ListView):
    template_name = "dashboard/feedback_list.html"
    model = Feedback
    paginate_by = 10
    context_object_name = "feedback_entries"

    def get_queryset(self):
        self.filter_form = FeedbackFilterForm(self.request.GET or None)
        if self.filter_form.is_valid():
            return filtered_feedback_queryset(self.request.user, self.filter_form.cleaned_data)
        return scoped_feedback_queryset(self.request.user)

    def get_context_data(self, **kwargs):
        context = super().get_context_data(**kwargs)
        context["filter_form"] = self.filter_form
        query_params = self.request.GET.copy()
        query_params.pop("page", None)
        context["current_filters"] = query_params.urlencode()
        return context


class FeedbackDetailView(DashboardAccessMixin, DetailView):
    template_name = "dashboard/feedback_detail.html"
    model = Feedback
    context_object_name = "entry"

    def get_queryset(self):
        return scoped_feedback_queryset(self.request.user)

    def get_context_data(self, **kwargs):
        context = super().get_context_data(**kwargs)
        entry = self.object
        context["sections"] = [
            (
                "Response overview",
                [
                    ("Submitted", entry.created_at.strftime("%Y-%m-%d %H:%M")),
                    ("Submitted on", entry.submitted_on.strftime("%d/%m/%Y") if entry.submitted_on else "Not provided"),
                    ("Facility", entry.facility.name),
                    ("District", entry.facility.district),
                    ("Province", entry.facility.province),
                    ("Rating", entry.rating),
                    ("Category", display_choice(entry, "category")),
                    ("Submission source", entry.get_submission_source_display()),
                    ("Collection session", entry.collection_session.session_code if entry.collection_session_id else "Not linked"),
                ],
            ),
            (
                "Respondent and visit details",
                [
                    ("Age group", display_choice(entry, "age_group")),
                    ("Gender", display_choice(entry, "gender")),
                    ("Distance from facility", display_choice(entry, "distance")),
                    ("Main service for today", display_choice(entry, "service")),
                    ("Service other", display_text(entry.service_other)),
                    ("Difficulty", display_choice_list(entry.difficulty, Feedback.Difficulty.choices)),
                ],
            ),
            (
                "Service coverage",
                [
                    ("Received service", display_choice(entry, "received_service")),
                    ("Reason not received", display_choice(entry, "reason_not_received")),
                    ("Reason not received other", display_text(entry.reason_not_received_other)),
                    ("Referral", display_choice(entry, "referral")),
                    ("Facility type", display_choice(entry, "facility_type")),
                    ("Facility type other", display_text(entry.facility_type_other)),
                ],
            ),
            (
                "Costs and access",
                [
                    ("Paid today", display_choice(entry, "payment")),
                    ("Insurance", display_choice(entry, "insurance")),
                    ("No insurance reason", display_choice(entry, "no_insurance_reason")),
                    ("No insurance reason other", display_text(entry.no_insurance_reason_other)),
                    ("Cash payment", display_choice(entry, "cash_payment")),
                    ("Cash payment other", display_text(entry.cash_payment_other)),
                    ("Cost affected care", display_choice(entry, "cost")),
                ],
            ),
            (
                "Quality and UHC",
                [
                    ("Got medicines", display_choice(entry, "medicines")),
                    ("Would revisit", display_choice(entry, "revisit")),
                    ("Equal chance of getting care", display_choice(entry, "chance")),
                    ("Reason not chance", display_choice(entry, "reason_not_chance")),
                    ("Reason not chance other", display_text(entry.reason_not_chance_other)),
                    ("What should change", display_choice(entry, "change")),
                    ("Change other", display_text(entry.change_other)),
                ],
            ),
            (
                "Comments",
                [
                    ("Additional comments", display_text(entry.comment)),
                    ("Anything else", display_choice(entry, "aob")),
                    ("Anything else detail", display_text(entry.aob_other)),
                ],
            ),
        ]
        return context


class FacilityListView(DashboardAccessMixin, ListView):
    template_name = "dashboard/facility_list.html"
    model = Facility
    paginate_by = 10
    context_object_name = "facilities"

    def get_queryset(self):
        queryset = Facility.objects.all()
        if not self.request.user.is_staff:
            profile = get_or_create_dashboard_profile(self.request.user)
            if profile.is_dashboard_user and profile.facility_id:
                queryset = queryset.filter(pk=profile.facility_id)
            else:
                return queryset.none()

        self.search_query = (self.request.GET.get("search") or "").strip()
        if self.search_query:
            queryset = queryset.filter(
                Q(name__icontains=self.search_query)
                | Q(district__icontains=self.search_query)
                | Q(province__icontains=self.search_query)
            )

        return queryset

    def get_context_data(self, **kwargs):
        context = super().get_context_data(**kwargs)
        context["search_query"] = getattr(self, "search_query", "")
        query_params = self.request.GET.copy()
        query_params.pop("page", None)
        context["current_filters"] = query_params.urlencode()
        return context


class FacilityCreateView(StaffRequiredMixin, CreateView):
    template_name = "dashboard/facility_form.html"
    model = Facility
    form_class = FacilityForm
    success_url = reverse_lazy("dashboard:facility_list")

    def form_valid(self, form):
        messages.success(self.request, "Facility created successfully.")
        return super().form_valid(form)

    def get_context_data(self, **kwargs):
        context = super().get_context_data(**kwargs)
        context["province_district_map"] = ZAMBIA_PROVINCES_AND_DISTRICTS
        return context


class FacilityUpdateView(StaffRequiredMixin, UpdateView):
    template_name = "dashboard/facility_form.html"
    model = Facility
    form_class = FacilityForm
    success_url = reverse_lazy("dashboard:facility_list")

    def form_valid(self, form):
        messages.success(self.request, "Facility updated successfully.")
        return super().form_valid(form)

    def get_context_data(self, **kwargs):
        context = super().get_context_data(**kwargs)
        context["province_district_map"] = ZAMBIA_PROVINCES_AND_DISTRICTS
        return context


class FacilityDetailView(DashboardAccessMixin, DetailView):
    template_name = "dashboard/facility_detail.html"
    model = Facility
    context_object_name = "facility"

    def get_queryset(self):
        queryset = Facility.objects.all()
        if self.request.user.is_staff:
            return queryset

        profile = get_or_create_dashboard_profile(self.request.user)
        if profile.is_dashboard_user and profile.facility_id:
            return queryset.filter(pk=profile.facility_id)
        return queryset.none()


class FacilityDeleteView(StaffRequiredMixin, DeleteView):
    template_name = "dashboard/facility_confirm_delete.html"
    model = Facility
    success_url = reverse_lazy("dashboard:facility_list")
    context_object_name = "facility"

    def form_valid(self, form):
        messages.success(self.request, "Facility deleted successfully.")
        return super().form_valid(form)


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


def export_feedback_csv(request):
    if not request.user.is_authenticated:
        return redirect_to_login(request.get_full_path())
    if not (request.user.is_staff or get_or_create_dashboard_profile(request.user).is_dashboard_user):
        return HttpResponse(status=403)

    queryset = filtered_feedback_queryset(request.user, request.GET).select_related("facility")
    response = HttpResponse(content_type="text/csv")
    response["Content-Disposition"] = 'attachment; filename="feedback-export.csv"'


    writer = csv.writer(response)
    writer.writerow([label for label, _getter in EXPORT_COLUMNS])


    for entry in queryset:
        writer.writerow(export_row(entry))


    return response


def export_feedback_excel(request):
    if not request.user.is_authenticated:
        return redirect_to_login(request.get_full_path())
    if not (request.user.is_staff or get_or_create_dashboard_profile(request.user).is_dashboard_user):
        return HttpResponse(status=403)

    from openpyxl import Workbook

    queryset = filtered_feedback_queryset(request.user, request.GET).select_related("facility")
    workbook = Workbook()
    sheet = workbook.active
    sheet.title = "Feedback"
    sheet.append([label for label, _getter in EXPORT_COLUMNS])

    for entry in queryset:
        sheet.append(export_row(entry))

    response = HttpResponse(
        content_type="application/vnd.openxmlformats-officedocument.spreadsheetml.sheet"
    )
    response["Content-Disposition"] = 'attachment; filename="feedback-export.xlsx"'
    workbook.save(response)
    return response


class DashboardUserListView(StaffRequiredMixin, ListView):
    template_name = "dashboard/user_list.html"
    context_object_name = "users"
    model = User
    paginate_by = 10

    def get_queryset(self):
        self.search_query = (self.request.GET.get("search") or "").strip()
        queryset = User.objects.order_by("username")
        if self.search_query:
            queryset = queryset.filter(
                Q(username__icontains=self.search_query)
                | Q(email__icontains=self.search_query)
                | Q(first_name__icontains=self.search_query)
                | Q(last_name__icontains=self.search_query)
            )
        users = list(queryset)
        for user in users:
            get_or_create_dashboard_profile(user)
        return users

    def get_context_data(self, **kwargs):
        context = super().get_context_data(**kwargs)
        context["search_query"] = getattr(self, "search_query", "")
        query_params = self.request.GET.copy()
        query_params.pop("page", None)
        context["current_filters"] = query_params.urlencode()
        return context


class DashboardUserCreateView(StaffRequiredMixin, FormView):
    template_name = "dashboard/user_form.html"
    form_class = DashboardUserCreationForm
    success_url = reverse_lazy("dashboard:user_list")

    def form_valid(self, form):
        form.save()
        messages.success(self.request, "User created successfully.")
        return super().form_valid(form)


class DashboardUserUpdateView(StaffRequiredMixin, UpdateView):
    template_name = "dashboard/user_edit.html"
    model = User
    form_class = DashboardUserUpdateForm
    context_object_name = "target_user"
    success_url = reverse_lazy("dashboard:user_list")

    def form_valid(self, form):
        messages.success(self.request, "User updated successfully.")
        return super().form_valid(form)


class DashboardUserPasswordResetView(StaffRequiredMixin, FormView):
    template_name = "dashboard/user_password_reset.html"
    form_class = DashboardUserPasswordResetForm
    success_url = reverse_lazy("dashboard:user_list")

    def dispatch(self, request, *args, **kwargs):
        self.target_user = get_object_or_404(User, pk=kwargs["pk"])
        return super().dispatch(request, *args, **kwargs)

    def get_form_kwargs(self):
        kwargs = super().get_form_kwargs()
        kwargs["user"] = self.target_user
        return kwargs

    def form_valid(self, form):
        form.save()
        messages.success(
            self.request,
            f"Password reset successfully for {self.target_user.username}.",
        )
        return super().form_valid(form)

    def get_context_data(self, **kwargs):
        context = super().get_context_data(**kwargs)
        context["target_user"] = self.target_user
        return context


class DashboardUserDeleteView(StaffRequiredMixin, DeleteView):
    template_name = "dashboard/user_confirm_delete.html"
    model = User
    success_url = reverse_lazy("dashboard:user_list")
    context_object_name = "target_user"

    def dispatch(self, request, *args, **kwargs):
        self.object = self.get_object()
        if self.object.is_staff:
            messages.error(request, "Admin accounts cannot be deleted from user management.")
            return redirect("dashboard:user_list")
        return super().dispatch(request, *args, **kwargs)

    def form_valid(self, form):
        username = self.object.username
        messages.success(self.request, f"User account {username} deleted successfully.")
        return super().form_valid(form)
