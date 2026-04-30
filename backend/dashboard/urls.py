from django.urls import path

from . import views

app_name = "dashboard"

urlpatterns = [
    path("", views.DashboardHomeView.as_view(), name="home"),
    path("feedback/", views.FeedbackListView.as_view(), name="feedback_list"),
    path("feedback/export/csv/", views.export_feedback_csv, name="export_csv"),
    path("feedback/export/excel/", views.export_feedback_excel, name="export_excel"),
    path("facilities/", views.FacilityListView.as_view(), name="facility_list"),
    path("facilities/new/", views.FacilityCreateView.as_view(), name="facility_create"),
    path("facilities/upload/", views.FacilityBulkUploadView.as_view(), name="facility_bulk_upload"),
    path("facilities/<int:pk>/edit/", views.FacilityUpdateView.as_view(), name="facility_update"),
    path("facilities/<int:pk>/", views.FacilityDetailView.as_view(), name="facility_detail"),
]
