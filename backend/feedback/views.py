from django.contrib import messages
from django.db import transaction
from django.shortcuts import redirect, render

from facilities.models import Facility
from .forms import FeedbackForm
from .models import Feedback
from .rate_limit import check_submission_rate

FEEDBACK_FACILITY_SESSION_KEY = "feedback_facility_id"


def _get_selected_facility(form):
    initial_facility = form.fields["facility"].initial
    if not initial_facility:
        return None

    try:
        return form.fields["facility"].queryset.get(pk=initial_facility)
    except Facility.DoesNotExist:
        return None


def _build_feedback_base_data(cleaned_data):
    excluded_fields = {"facility", "comment", "medicine"}
    return {
        field_name: value
        for field_name, value in cleaned_data.items()
        if field_name not in excluded_fields
    }


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


def submit_feedback(request, facility_id=None):
    categories = Feedback.Category.choices

    facility_id = _resolve_facility_id(request, facility_id=facility_id)

    if request.method == "POST":
        post_data = request.POST.copy()
        if facility_id:
            post_data["facility"] = str(facility_id)
        form = FeedbackForm(post_data, facility_id=facility_id)

        if form.is_valid():
            if not check_submission_rate(request):
                form.add_error(None, "Too many submissions from this connection. Please try again later.")
            else:
                facility = form.cleaned_data["facility"]
                feedback_base_data = _build_feedback_base_data(form.cleaned_data)
                pending_entries = []

                for category_value, _category_label in categories:
                    rating_value = request.POST.get(f"rating_{category_value}")
                    comment_value = request.POST.get(f"comment_{category_value}")

                    if rating_value:
                        pending_entries.append(
                            Feedback(
                                facility=facility,
                                category=category_value,
                                rating=int(rating_value),
                                comment=comment_value or "",
                                **feedback_base_data,
                            )
                        )

                if not pending_entries:
                    form.add_error(None, "Please rate at least one category.")
                else:
                    with transaction.atomic():
                        Feedback.objects.bulk_create(pending_entries)

                    request.session[FEEDBACK_FACILITY_SESSION_KEY] = str(facility.pk)
                    messages.success(request, "Thank you. Your feedback has been submitted.")
                    return redirect("feedback:thank_you")
    else:
        form = FeedbackForm(facility_id=facility_id)

    context = {
        "form": form,
        "categories": categories,
        "selected_facility": _get_selected_facility(form),
    }
    return render(request, "feedback/form.html", context)


def thank_you(request):
    facility_id = request.session.get(FEEDBACK_FACILITY_SESSION_KEY)
    facility = None
    if facility_id:
        try:
            facility = Facility.objects.get(pk=facility_id)
        except Facility.DoesNotExist:
            request.session.pop(FEEDBACK_FACILITY_SESSION_KEY, None)

    return render(request, "feedback/thank_you.html", {"selected_facility": facility})
