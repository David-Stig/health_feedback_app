from django.db import transaction
from django.utils import timezone

from feedback.models import Feedback, RatingResponse


def create_feedback_entries_from_cleaned_data(
    *,
    facility,
    cleaned_data: dict,
    ratings: dict,
    comments: dict,
    submission_source: str,
    collection_session=None,
    import_batch=None,
    captured_by=None,
    submitted_on=None,
    fingerprint: str = "",
    consent_acknowledged=None,
    consent_version=None,
):
    excluded_fields = {"facility", "comment", "medicine", "consent_acknowledged"}
    submission_data = {
        field_name: value
        for field_name, value in cleaned_data.items()
        if field_name not in excluded_fields
    }
    effective_submitted_on = submitted_on or timezone.localdate()
    normalized_ratings = []
    for category_value, rating_value in ratings.items():
        if not rating_value:
            continue
        normalized_ratings.append(
            {
                "category": category_value,
                "rating": int(rating_value),
                "comment": comments.get(category_value, "") or "",
            }
        )

    has_meaningful_response = bool(normalized_ratings)
    if not has_meaningful_response:
        return None

    with transaction.atomic():
        submission = Feedback.objects.create(
            facility=facility,
            submission_source=submission_source,
            collection_session=collection_session,
            import_batch=import_batch,
            captured_by=captured_by,
            submitted_on=effective_submitted_on,
            fingerprint=fingerprint,
            consent_acknowledged=consent_acknowledged,
            consent_version=consent_version,
            **submission_data,
        )
        RatingResponse.objects.bulk_create(
            [
                RatingResponse(
                    submission=submission,
                    category=item["category"],
                    rating=item["rating"],
                    comment=item["comment"],
                )
                for item in normalized_ratings
            ]
        )
    return submission
