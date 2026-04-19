from django.contrib import messages
from django.shortcuts import redirect, render

from facilities.models import Facility
from .forms import FeedbackForm
from .models import Feedback


def submit_feedback(request):
    categories = Feedback.Category.choices
    selected_facility = None

    facility_id = (
        request.GET.get("facility_id")
        or request.GET.get("facility")
        or request.POST.get("facility")
    )

    if request.method == "POST":
        form = FeedbackForm(request.POST, facility_id=facility_id)

        if form.is_valid():
            facility = form.cleaned_data["facility"]
            age_group = form.cleaned_data.get("age_group")
            gender = form.cleaned_data.get("gender")

            saved_count = 0

            for category_value, category_label in categories:
                rating_value = request.POST.get(f"rating_{category_value}")
                comment_value = request.POST.get(f"comment_{category_value}")

                if rating_value:
                    Feedback.objects.create(
                        facility=facility,
                        category=category_value,
                        rating=int(rating_value),
                        comment=comment_value or "",
                        age_group=age_group or "",
                        gender=gender or "",
                    )
                    saved_count += 1

            if saved_count == 0:
                form.add_error(None, "Please rate at least one category.")
            else:
                messages.success(request, "Thank you. Your feedback has been submitted.")
                return redirect("feedback:thank_you")
    else:
        form = FeedbackForm(facility_id=facility_id)

    initial_facility = form.fields["facility"].initial
    if initial_facility:
        try:
            selected_facility = form.fields["facility"].queryset.get(pk=initial_facility)
        except Facility.DoesNotExist:
            selected_facility = None
        except Exception:
            selected_facility = None

    context = {
        "form": form,
        "categories": categories,
        "selected_facility": selected_facility,
    }
    return render(request, "feedback/form.html", context)


def thank_you(request):
    return render(request, "feedback/thank_you.html")
