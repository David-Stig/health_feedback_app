from django.conf import settings
from django.core.cache import cache


def client_ip_from_request(request) -> str:
    forwarded = request.META.get("HTTP_X_FORWARDED_FOR")
    if forwarded:
        return forwarded.split(",")[0].strip()
    return request.META.get("REMOTE_ADDR", "unknown")


def check_submission_rate(request) -> bool:
    ip_address = client_ip_from_request(request)
    cache_key = f"feedback-rate:{ip_address}"
    current = cache.get(cache_key, 0)
    if current >= settings.RATE_LIMIT_SUBMISSIONS:
        return False

    # A small cache-based throttle is enough for MVP spam protection without slowing honest users down.
    cache.set(cache_key, current + 1, timeout=settings.RATE_LIMIT_WINDOW_SECONDS)
    return True
