from __future__ import annotations

from collections import Counter

from django.db.models import Avg, Count, Q

from dashboard.mixins import accessible_facilities_for_user
from feedback.models import Feedback, RatingResponse


TEXT_FIELDS = [
    "comment",
    "change_other",
    "aob_other",
    "reason_not_received_other",
    "reason_not_chance_other",
    "service_other",
    "facility_type_other",
    "no_insurance_reason_other",
    "cash_payment_other",
]


def feedback_queryset_for_scope(
    user,
    *,
    facility=None,
    period_start=None,
    period_end=None,
    collection_session=None,
    submission_source="",
):
    facility_ids = accessible_facilities_for_user(user).values_list("pk", flat=True)
    queryset = Feedback.objects.filter(is_active=True, facility_id__in=facility_ids).select_related(
        "facility",
        "collection_session",
    ).prefetch_related("rating_responses")
    if facility:
        queryset = queryset.filter(facility=facility)
    if period_start:
        queryset = queryset.filter(created_at__date__gte=period_start)
    if period_end:
        queryset = queryset.filter(created_at__date__lte=period_end)
    if collection_session:
        queryset = queryset.filter(collection_session=collection_session)
    if submission_source:
        queryset = queryset.filter(submission_source=submission_source)
    return queryset


def rating_breakdown(queryset):
    return list(
        RatingResponse.objects.filter(submission__in=queryset)
        .values("category")
        .annotate(
            total=Count("id"),
            average_rating=Avg("rating"),
            low_ratings=Count("id", filter=Q(rating__lte=2)),
        )
        .order_by("category")
    )


def structured_choice_breakdown(queryset, field_name):
    return list(
        queryset.exclude(**{field_name: ""})
        .values(field_name)
        .annotate(total=Count("id"))
        .order_by("-total")
    )


def facility_breakdown(queryset):
    return list(
        queryset.values("facility__name")
        .annotate(total=Count("id"), average_rating=Avg("rating_responses__rating"))
        .order_by("-total", "facility__name")
    )


def text_records(queryset):
    records = []
    for submission in queryset:
        for field_name in TEXT_FIELDS:
            value = getattr(submission, field_name, "")
            if value and str(value).strip():
                records.append(
                    {
                        "submission_id": submission.pk,
                        "facility": submission.facility.name,
                        "field_name": field_name,
                        "text": str(value).strip(),
                        "created_at": submission.created_at,
                    }
                )
        for rating_response in submission.rating_responses.all():
            if rating_response.comment and rating_response.comment.strip():
                records.append(
                    {
                        "submission_id": submission.pk,
                        "facility": submission.facility.name,
                        "field_name": f"rating:{rating_response.category}",
                        "text": rating_response.comment.strip(),
                        "created_at": rating_response.created_at,
                    }
                )
    return records


def source_counter(records):
    return Counter(record["field_name"] for record in records)
