import hashlib
import json
from datetime import date

from feedback.models import Feedback


class DuplicateStatus:
    NEW = "new"
    POSSIBLE_DUPLICATE = "possible_duplicate"
    EXACT_DUPLICATE = "exact_duplicate"


def normalize_text(value) -> str:
    if value is None:
        return ""
    return " ".join(str(value).strip().lower().split())


def build_feedback_fingerprint(row_data: dict) -> str:
    normalized_payload = {
        "facility": row_data.get("facility_id"),
        "submitted_on": row_data.get("submitted_on").isoformat()
        if isinstance(row_data.get("submitted_on"), date)
        else normalize_text(row_data.get("submitted_on")),
        "ratings": row_data.get("ratings", {}),
        "comments": {
            key: normalize_text(value) for key, value in (row_data.get("comments") or {}).items()
        },
        "respondent": {
            "gender": normalize_text(row_data.get("gender")),
            "age_group": normalize_text(row_data.get("age_group")),
            "distance": normalize_text(row_data.get("distance")),
            "service": normalize_text(row_data.get("service")),
        },
    }
    raw = json.dumps(normalized_payload, sort_keys=True, ensure_ascii=True)
    return hashlib.sha256(raw.encode("utf-8")).hexdigest()


def classify_duplicate(fingerprint: str, facility_id: int):
    exact_exists = Feedback.objects.filter(
        fingerprint=fingerprint,
        facility_id=facility_id,
        is_active=True,
    ).exists()
    if exact_exists:
        return DuplicateStatus.EXACT_DUPLICATE

    possible_exists = Feedback.objects.filter(
        facility_id=facility_id,
        is_active=True,
        fingerprint__startswith=fingerprint[:16],
    ).exists()
    if possible_exists:
        return DuplicateStatus.POSSIBLE_DUPLICATE

    return DuplicateStatus.NEW
