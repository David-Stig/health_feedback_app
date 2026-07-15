from django.urls import path

from . import views

app_name = "feedback"

urlpatterns = [
    path("", views.submit_feedback, name="submit"),
    path("facility/<slug:facility_slug>-<int:facility_id>/", views.submit_feedback, name="facility_submit"),
    path("facility/<int:facility_id>/", views.submit_feedback_legacy, name="facility_submit_legacy"),
    path("thank-you/", views.thank_you, name="thank_you"),
]
