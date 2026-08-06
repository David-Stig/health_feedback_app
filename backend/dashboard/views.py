import csv
from io import TextIOWrapper
from datetime import timedelta
from collections import OrderedDict

from django.contrib import messages
from django.contrib.auth import get_user_model
from django.contrib.auth import update_session_auth_hash
from django.contrib.auth.views import redirect_to_login
from django.db import transaction
from django.db.models import Avg, Case, CharField, Count, Q, Value, When
from django.db.models.functions import TruncDate
from django.http import HttpResponse
from django.shortcuts import get_object_or_404, redirect
from django.urls import reverse_lazy
from django.utils import timezone
from django.views.generic import CreateView, DeleteView, DetailView, FormView, ListView, TemplateView, UpdateView

from facilities.forms import BulkFacilityUploadForm, FacilityForm, ZAMBIA_PROVINCES_AND_DISTRICTS
from facilities.models import Facility
from feedback.models import Feedback, RatingResponse

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


def build_pagination_window(page_obj, window_size=5):
    if not page_obj:
        return []

    total_pages = page_obj.paginator.num_pages
    if total_pages <= window_size:
        return list(page_obj.paginator.page_range)

    half_window = window_size // 2
    start = max(page_obj.number - half_window, 1)
    end = start + window_size - 1

    if end > total_pages:
        end = total_pages
        start = max(end - window_size + 1, 1)

    return list(range(start, end + 1))

DASHBOARD_LABEL_OVERRIDES = {
    ("insurance", Feedback.INSURANCE.NONE): "No insurance used",
}

RATING_CATEGORY_DEFINITIONS = [
    {
        "key": "waiting_time",
        "full_label": "Waiting time before being seen",
        "short_label": "Waiting Time",
        "source_values": [
            Feedback.Category.WAITING_TIME,
            "Waiting Time",
        ],
    },
    {
        "key": "respect_dignity",
        "full_label": "Respect and dignity from staff",
        "short_label": "Respect & Dignity",
        "source_values": [
            Feedback.Category.STAFF_ATTITUDE,
            "Staff Attitude",
        ],
    },
    {
        "key": "cleanliness",
        "full_label": "Cleanliness of the health facility",
        "short_label": "Cleanliness",
        "source_values": [
            Feedback.Category.CLEANLINESS,
            "Cleanliness",
        ],
    },
    {
        "key": "health_explanation",
        "full_label": "Explanation of your illness and treatment",
        "short_label": "Health Explanation",
        "source_values": [
            Feedback.Category.EXPLANATION,
        ],
    },
    {
        "key": "medication",
        "full_label": "Availability of Medication",
        "short_label": "Medication",
        "source_values": [
            Feedback.Category.MEDICATION,
        ],
    },
]

CHANGE_LABEL_DEFINITIONS = {
    Feedback.CHANGE.MORE_WORKERS: {
        "short_label": "Health workers",
        "full_label": "More health workers available",
    },
    Feedback.CHANGE.MORE_MEDICINES: {
        "short_label": "Medicines",
        "full_label": "More medicines in stock",
    },
    Feedback.CHANGE.WAITING_TIME: {
        "short_label": "Waiting Time",
        "full_label": "Shorter waiting time",
    },
    Feedback.CHANGE.LOWER_COST: {
        "short_label": "Lower/No Costs",
        "full_label": "Lower costs / no fees",
    },
    Feedback.CHANGE.STAFF_ATTITUDE: {
        "short_label": "Staff Attitude",
        "full_label": "Better staff attitude",
    },
    Feedback.CHANGE.OPENING_HOURS: {
        "short_label": "Operating Hours",
        "full_label": "Longer opening hours",
    },
    Feedback.CHANGE.OTHER: {
        "short_label": "Other",
        "full_label": "Other",
    },
}

INSURANCE_LABEL_DEFINITIONS = {
    Feedback.INSURANCE.NHIMA: {
        "short_label": "NHIMA",
        "full_label": "NHIMA (National Health Insurance)",
    },
    Feedback.INSURANCE.PRIVATE: {
        "short_label": "Private",
        "full_label": "Private Insurance",
    },
    Feedback.INSURANCE.BOTH: {
        "short_label": "Both",
        "full_label": "Both NHIMA and private",
    },
    Feedback.INSURANCE.NONE: {
        "short_label": "None",
        "full_label": "No insurance used",
    },
    Feedback.INSURANCE.NOT_SURE: {
        "short_label": "Not Sure",
        "full_label": "Not sure",
    },
}

RATING_EXPORT_COLUMNS = [
    (choice_value, choice_label) for choice_value, choice_label in Feedback.Category.choices
]

EXPORT_COLUMNS = [
    ("Date", lambda entry: entry.created_at.strftime("%Y-%m-%d %H:%M")),
    ("Submitted on", lambda entry: entry.submitted_on.strftime("%Y-%m-%d") if entry.submitted_on else ""),
    ("Facility", lambda entry: entry.facility.name),
    ("District", lambda entry: entry.facility.district),
    ("Province", lambda entry: entry.facility.province),
    ("Submission source", lambda entry: entry.get_submission_source_display()),
    ("Collection session", lambda entry: entry.collection_session.session_code if entry.collection_session_id else ""),
    ("Ratings answered", lambda entry: entry.rating_response_count),
    ("Average rating", lambda entry: round(entry.average_rating_score or 0, 2) if entry.average_rating_score else ""),
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
EXPORT_COLUMNS += [
    (f"{label} rating", lambda entry, category=category: build_rating_map(entry).get(category, {}).get("rating", ""))
    for category, label in RATING_EXPORT_COLUMNS
]
EXPORT_COLUMNS += [
    (f"{label} comment", lambda entry, category=category: build_rating_map(entry).get(category, {}).get("comment", ""))
    for category, label in RATING_EXPORT_COLUMNS
]


def export_row(entry):
    return [getter(entry) for _label, getter in EXPORT_COLUMNS]


def build_rating_map(entry):
    responses = getattr(entry, "_prefetched_objects_cache", {}).get("rating_responses")
    if responses is None:
        responses = entry.rating_responses.all()
    return {
        response.category: {
            "rating": response.rating,
            "comment": response.comment,
        }
        for response in responses
    }


def choice_breakdown(queryset, field_name, choices, *, include_blank=False):
    choice_map = dict(choices)
    breakdown = list(
        queryset.values(field_name).annotate(total=Count("id", distinct=True)).order_by("-total")
    )

    items = []
    for item in breakdown:
        raw_value = item[field_name]
        if not raw_value and not include_blank:
            continue
        label = choice_map.get(raw_value, raw_value or "Not provided")
        items.append({"value": raw_value, "label": label, "total": item["total"]})
    return items


def count_answered_submissions(queryset, field_name):
    return queryset.exclude(**{f"{field_name}__isnull": True}).exclude(**{field_name: ""}).count()


def stable_sorted_breakdown(items, choices):
    order_map = {value: index for index, (value, _label) in enumerate(choices)}
    return sorted(
        items,
        key=lambda item: (-item["total"], order_map.get(item["value"], len(order_map)), item["label"].lower()),
    )


def build_single_choice_chart_data(queryset, field_name, choices, *, include_blank=False, summary_label="respondents"):
    answered_total = count_answered_submissions(queryset, field_name)
    items = choice_breakdown(queryset, field_name, choices, include_blank=include_blank)
    for item in items:
        override = DASHBOARD_LABEL_OVERRIDES.get((field_name, item["value"]))
        if override:
            item["label"] = override
        if field_name == "insurance":
            labels = INSURANCE_LABEL_DEFINITIONS.get(item["value"])
            if labels:
                item["short_label"] = labels["short_label"]
                item["full_label"] = labels["full_label"]
        item["percentage"] = round((item["total"] / answered_total) * 100, 1) if answered_total else 0
    items = stable_sorted_breakdown(items, choices)
    return {
        "items": items,
        "answered_total": answered_total,
        "summary": f"{answered_total} {summary_label}",
        "note": "",
        "question_type": "single",
    }


def build_multi_choice_chart_data(queryset, field_name, choices, *, summary_noun="selections"):
    answered_total = count_answered_submissions(queryset, field_name)
    items = choice_breakdown(queryset, field_name, choices)
    selection_total = sum(item["total"] for item in items)
    for item in items:
        item["percentage"] = round((item["total"] / answered_total) * 100, 1) if answered_total else 0
        if field_name == "change":
            labels = CHANGE_LABEL_DEFINITIONS.get(item["value"])
            if labels:
                item["short_label"] = labels["short_label"]
                item["full_label"] = labels["full_label"]
    items = stable_sorted_breakdown(items, choices)
    return {
        "items": items,
        "answered_total": answered_total,
        "selection_total": selection_total,
        "summary": f"{selection_total} {summary_noun} from {answered_total} submissions" if answered_total else f"0 {summary_noun}",
        "note": "Multiple selections allowed",
        "question_type": "multiple",
    }


def build_rating_category_chart_data(rating_queryset):
    normalization_cases = [
        When(category__in=definition["source_values"], then=Value(definition["key"]))
        for definition in RATING_CATEGORY_DEFINITIONS
    ]
    aggregated = {
        row["normalized_category"]: row["total"]
        for row in (
            rating_queryset.annotate(
                normalized_category=Case(
                    *normalization_cases,
                    default=Value(None),
                    output_field=CharField(),
                )
            )
            .exclude(normalized_category__isnull=True)
            .values("normalized_category")
            .annotate(total=Count("id"))
        )
    }

    items = []
    for definition in RATING_CATEGORY_DEFINITIONS:
        items.append(
            {
                "key": definition["key"],
                "full_label": definition["full_label"],
                "short_label": definition["short_label"],
                "total": aggregated.get(definition["key"], 0),
            }
        )
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
    queryset = (
        Feedback.objects.select_related("facility", "collection_session", "import_batch", "captured_by")
        .prefetch_related("rating_responses")
        .annotate(
            rating_response_total=Count("rating_responses", distinct=True),
            average_rating_value=Avg("rating_responses__rating"),
        )
        .filter(is_active=True)
        .order_by("-created_at", "-pk")
    )
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
        queryset = queryset.filter(rating_responses__category=params["category"]).distinct()
    if params.get("rating"):
        queryset = queryset.filter(rating_responses__rating=params["rating"]).distinct()
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
        queryset = queryset.filter(
            Q(comment__icontains=params["search"])
            | Q(rating_responses__comment__icontains=params["search"])
        ).distinct()

    return queryset.order_by("-created_at", "-pk")


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
            .annotate(total=Count("id", distinct=True), average_rating=Avg("rating_responses__rating"))
            .order_by("day")
        )

        gender_breakdown = list(
            feedback_qs.values("gender").annotate(total=Count("id", distinct=True)).order_by("-total")
        )
        distance_breakdown = list(
            feedback_qs.values("distance").annotate(total=Count("id", distinct=True)).order_by("-total")
        )
        rating_qs = RatingResponse.objects.filter(submission__in=feedback_qs)
        category_breakdown = build_rating_category_chart_data(rating_qs)
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
        insurance_chart = build_single_choice_chart_data(
            feedback_qs,
            "insurance",
            Feedback.INSURANCE.choices,
        )
        change_chart = build_multi_choice_chart_data(
            feedback_qs,
            "change",
            Feedback.CHANGE.choices,
        )
        insurance_breakdown = insurance_chart["items"]
        change_breakdown = change_chart["items"]
        reason_not_received_breakdown = choice_breakdown(
            feedback_qs,
            "reason_not_received",
            Feedback.ReasonNotReceived.choices,
        )
        facility_breakdown = list(
            feedback_qs.values("facility__name").annotate(total=Count("id", distinct=True)).order_by("-total")[:10]
        )
        province_breakdown = list(
            feedback_qs.values("facility__province").annotate(total=Count("id", distinct=True)).order_by("-total")
        )  

        context.update(
            {
                "total_submissions": total_submissions,
                "facility_count": Facility.objects.count(),
                "average_rating": round(rating_qs.aggregate(avg=Avg("rating"))["avg"] or 0, 2),
                "gender_breakdown": gender_breakdown,
                "category_breakdown": category_breakdown,
                "source_breakdown": source_breakdown,
                "received_service_breakdown": received_service_breakdown,
                "payment_breakdown": payment_breakdown,
                "medicines_breakdown": medicines_breakdown,
                "revisit_breakdown": revisit_breakdown,
                "insurance_breakdown": insurance_breakdown,
                "change_breakdown": change_breakdown,
                "insurance_chart_summary": insurance_chart["summary"],
                "insurance_chart_note": insurance_chart["note"],
                "insurance_short_labels": [item.get("short_label", item["label"]) for item in insurance_breakdown],
                "insurance_full_labels": [item.get("full_label", item["label"]) for item in insurance_breakdown],
                "insurance_percentages": [item["percentage"] for item in insurance_breakdown],
                "insurance_answered_total": insurance_chart["answered_total"],
                "change_chart_summary": change_chart["summary"],
                "change_chart_note": change_chart["note"],
                "change_short_labels": [item.get("short_label", item["label"]) for item in change_breakdown],
                "change_full_labels": [item.get("full_label", item["label"]) for item in change_breakdown],
                "change_percentages": [item["percentage"] for item in change_breakdown],
                "change_answered_total": change_chart["answered_total"],
                "change_selection_total": change_chart["selection_total"],
                "reason_not_received_breakdown": reason_not_received_breakdown,
                "facility_breakdown": facility_breakdown,
                "province_breakdown": province_breakdown,
                "trend_labels": [item["day"].strftime("%Y-%m-%d") for item in trend_data],
                "trend_totals": [item["total"] for item in trend_data],
                "trend_ratings": [round(item["average_rating"] or 0, 2) for item in trend_data],
                "gender_labels": [item["gender"] for item in gender_breakdown],
                "gender_totals": [item["total"] for item in gender_breakdown],
                "category_labels": [item["short_label"] for item in category_breakdown],
                "category_full_labels": [item["full_label"] for item in category_breakdown],
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
                "insurance_labels": [item.get("short_label", item["label"]) for item in insurance_breakdown],
                "insurance_totals": [item["total"] for item in insurance_breakdown],
                "change_labels": [item.get("short_label", item["label"]) for item in change_breakdown],
                "change_totals": [item["total"] for item in change_breakdown],
                "public_qr_total": feedback_qs.filter(submission_source=Feedback.SubmissionSource.QR_PUBLIC).count(),
                "assisted_total": feedback_qs.filter(submission_source=Feedback.SubmissionSource.ASSISTED_CAPTURE).count(),
                "active_session_total": Feedback.collection_session.field.related_model.objects.filter(status="active").count(),
                "total_rating_responses": rating_qs.count(),
                "average_ratings_per_submission": round((rating_qs.count() / total_submissions), 2) if total_submissions else 0,
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
        context["pagination_window"] = build_pagination_window(context["page_obj"])
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
                    ("Ratings answered", entry.rating_response_count),
                    ("Average rating", round(entry.average_rating_score, 2) if entry.average_rating_score else "Not provided"),
                    ("Submission source", entry.get_submission_source_display()),
                    ("Collection session", entry.collection_session.session_code if entry.collection_session_id else "Not linked"),
                ],
            ),
            (
                "Rating responses",
                [
                    (
                        dict(Feedback.Category.choices).get(response.category, response.category),
                        f"{response.rating}" + (f" - {display_text(response.comment, default='')}" if display_text(response.comment, default='') else ""),
                    )
                    for response in entry.rating_responses.all()
                ] or [("Ratings", "No rating responses recorded")],
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
        context["pagination_window"] = build_pagination_window(context["page_obj"])
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

    queryset = filtered_feedback_queryset(request.user, request.GET).select_related("facility").prefetch_related("rating_responses")
    response = HttpResponse(content_type="text/csv")
    response["Content-Disposition"] = 'attachment; filename="feedback-submissions-export.csv"'


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

    queryset = filtered_feedback_queryset(request.user, request.GET).select_related("facility").prefetch_related("rating_responses")
    workbook = Workbook()
    sheet = workbook.active
    sheet.title = "Feedback Submissions"
    sheet.append([label for label, _getter in EXPORT_COLUMNS])

    for entry in queryset:
        sheet.append(export_row(entry))

    response = HttpResponse(
        content_type="application/vnd.openxmlformats-officedocument.spreadsheetml.sheet"
    )
    response["Content-Disposition"] = 'attachment; filename="feedback-submissions-export.xlsx"'
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
        context["pagination_window"] = build_pagination_window(context["page_obj"])
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
