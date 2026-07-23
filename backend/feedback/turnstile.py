import json
import logging
from urllib.error import URLError
from urllib.parse import urlencode
from urllib.request import Request, urlopen

from django.conf import settings


logger = logging.getLogger(__name__)


def get_client_ip(request):
    forwarded_for = request.META.get("HTTP_X_FORWARDED_FOR")
    if forwarded_for:
        return forwarded_for.split(",")[0].strip()
    return request.META.get("REMOTE_ADDR", "")


def verify_turnstile(request):
    if not settings.TURNSTILE_ENABLED:
        return True, None

    token = request.POST.get("cf-turnstile-response", "").strip()
    if not token:
        return False, "Please complete the security check."

    payload = urlencode(
        {
            "secret": settings.TURNSTILE_SECRET_KEY,
            "response": token,
            "remoteip": get_client_ip(request),
        }
    ).encode("utf-8")

    verification_request = Request(
        settings.TURNSTILE_VERIFY_URL,
        data=payload,
        headers={"Content-Type": "application/x-www-form-urlencoded"},
        method="POST",
    )

    try:
        with urlopen(verification_request, timeout=10) as response:
            verification_data = json.loads(response.read().decode("utf-8"))
    except (URLError, TimeoutError, json.JSONDecodeError) as exc:
        logger.warning("Turnstile verification failed due to transport error: %s", exc)
        return False, "We could not verify the security check. Please try again."

    if verification_data.get("success"):
        return True, None

    logger.info(
        "Turnstile rejected submission",
        extra={"error_codes": verification_data.get("error-codes", [])},
    )
    return False, "Security verification failed. Please try again."
