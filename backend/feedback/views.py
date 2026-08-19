from django.contrib import messages
from django.conf import settings
from django.db import transaction
from django.shortcuts import get_object_or_404, redirect, render

from facilities.models import Facility
from .consent import get_consent_content
from .forms import FeedbackForm
from .models import Feedback
from .rate_limit import check_submission_rate
from .submission_service import create_feedback_entries_from_cleaned_data
from .turnstile import verify_turnstile

FEEDBACK_FACILITY_SESSION_KEY = "feedback_facility_id"


def _build_rating_state(request, categories):
    rating_values = {}
    rating_comments = {}
    for category_value, _category_label in categories:
        rating_values[category_value] = request.POST.get(f"rating_{category_value}", "")
        rating_comments[category_value] = request.POST.get(f"comment_{category_value}", "")
    return rating_values, rating_comments


def _get_selected_facility(form):
    initial_facility = form.fields["facility"].initial
    if not initial_facility:
        return None

    try:
        return form.fields["facility"].queryset.get(pk=initial_facility)
    except Facility.DoesNotExist:
        return None


def _resolve_facility_id(request, facility_id=None):
    if facility_id:
        request.session[FEEDBACK_FACILITY_SESSION_KEY] = str(facility_id)
        return str(facility_id)

    session_facility_id = request.session.get(FEEDBACK_FACILITY_SESSION_KEY)
    if request.method == "POST" and session_facility_id:
        return session_facility_id

    explicit_facility_id = (
        request.GET.get("facility_id")
        or request.GET.get("facility")
        or request.POST.get("facility")
    )
    if explicit_facility_id:
        request.session[FEEDBACK_FACILITY_SESSION_KEY] = explicit_facility_id
        return explicit_facility_id

    return session_facility_id


def submit_feedback(request, facility_slug=None, facility_id=None):
    categories = Feedback.Category.choices
    consent_content = get_consent_content()
    rating_values = {}
    rating_comments = {}

    facility_id = _resolve_facility_id(request, facility_id=facility_id)

    if request.method == "POST":
        post_data = request.POST.copy()
        if facility_id:
            post_data["facility"] = str(facility_id)
        form = FeedbackForm(post_data, facility_id=facility_id)
        rating_values, rating_comments = _build_rating_state(request, categories)

        if form.is_valid():
            turnstile_passed, turnstile_error = verify_turnstile(request)
            if not turnstile_passed:
                form.add_error(None, turnstile_error)
            elif not check_submission_rate(request):
                form.add_error(None, "Too many submissions from this connection. Please try again later.")
            else:
                facility = form.cleaned_data["facility"]
                ratings = {}
                comments = {}

                for category_value, _category_label in categories:
                    rating_value = request.POST.get(f"rating_{category_value}")
                    comment_value = request.POST.get(f"comment_{category_value}")

                    if rating_value:
                        ratings[category_value] = rating_value
                        comments[category_value] = comment_value or ""

                if not ratings:
                    form.add_error(None, "Please rate at least one category.")
                else:
                    create_feedback_entries_from_cleaned_data(
                        facility=facility,
                        cleaned_data=form.cleaned_data,
                        ratings=ratings,
                        comments=comments,
                        submission_source=Feedback.SubmissionSource.QR_PUBLIC,
                        consent_acknowledged=True,
                        consent_version=consent_content["version"],
                    )

                    request.session[FEEDBACK_FACILITY_SESSION_KEY] = str(facility.pk)
                    messages.success(request, "Thank you. Your feedback has been submitted.")
                    return redirect("feedback:thank_you")
    else:
        form = FeedbackForm(facility_id=facility_id)

    context = {
        "form": form,
        "categories": categories,
        "selected_facility": _get_selected_facility(form),
        "consent_content": consent_content,
        "rating_values": rating_values,
        "rating_comments": rating_comments,
        "turnstile_enabled": settings.TURNSTILE_ENABLED,
        "turnstile_site_key": settings.TURNSTILE_SITE_KEY,
    }
    return render(request, "feedback/form.html", context)


def submit_feedback_legacy(request, facility_id):
    facility = get_object_or_404(Facility, pk=facility_id)
    return redirect(
        "feedback:facility_submit",
        facility_slug=facility.get_feedback_slug(),
        facility_id=facility.pk,
    )


def thank_you(request):
    facility_id = request.session.get(FEEDBACK_FACILITY_SESSION_KEY)
    facility = None
    if facility_id:
        try:
            facility = Facility.objects.get(pk=facility_id)
        except Facility.DoesNotExist:
            request.session.pop(FEEDBACK_FACILITY_SESSION_KEY, None)

    return render(request, "feedback/thank_you.html", {"selected_facility": facility})
