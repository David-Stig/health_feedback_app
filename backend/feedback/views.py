from django.contrib import messages
from django.shortcuts import redirect, render

from facilities.models import Facility

from .forms import FeedbackForm
from .rate_limit import check_submission_rate


def submit_feedback(request):
    facility_id = request.GET.get("facility_id") or request.POST.get("facility")
    selected_facility = None
    if facility_id:
        selected_facility = Facility.objects.filter(pk=facility_id).first()

    if request.method == "POST":
        form = FeedbackForm(request.POST, facility_id=facility_id)
        if form.is_valid():
            if not check_submission_rate(request):
                messages.error(request, "Too many submissions from this network. Please try again later.")
            else:
                form.save()
                return redirect("feedback:thank_you")
    else:
        form = FeedbackForm(facility_id=facility_id)

    return render(
        request,
        "feedback/form.html",
        {
            "form": form,
            "selected_facility": selected_facility,
        },
    )


def feedback_thank_you(request):
    return render(request, "feedback/thank_you.html")
