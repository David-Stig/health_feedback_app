from django.db import transaction
from django.utils import timezone

from feedback.models import Feedback


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
):
    excluded_fields = {"facility", "comment", "medicine"}
    feedback_base_data = {
        field_name: value
        for field_name, value in cleaned_data.items()
        if field_name not in excluded_fields
    }
    effective_submitted_on = submitted_on or timezone.localdate()

    pending_entries = []
    for category_value, rating_value in ratings.items():
        if not rating_value:
            continue
        pending_entries.append(
            Feedback(
                facility=facility,
                category=category_value,
                rating=int(rating_value),
                comment=comments.get(category_value, "") or "",
                submission_source=submission_source,
                collection_session=collection_session,
                import_batch=import_batch,
                captured_by=captured_by,
                submitted_on=effective_submitted_on,
                fingerprint=fingerprint,
                **feedback_base_data,
            )
        )

    if not pending_entries:
        return []

    with transaction.atomic():
        return Feedback.objects.bulk_create(pending_entries)
