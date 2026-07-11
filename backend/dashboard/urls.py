from django.urls import path

from . import views

app_name = "dashboard"

urlpatterns = [
    path("", views.DashboardHomeView.as_view(), name="home"),
    path("feedback/", views.FeedbackListView.as_view(), name="feedback_list"),
    path("feedback/<int:pk>/", views.FeedbackDetailView.as_view(), name="feedback_detail"),
    path("feedback/export/csv/", views.export_feedback_csv, name="export_csv"),
    path("feedback/export/excel/", views.export_feedback_excel, name="export_excel"),
    path("facilities/", views.FacilityListView.as_view(), name="facility_list"),
    path("facilities/new/", views.FacilityCreateView.as_view(), name="facility_create"),
    path("facilities/upload/", views.FacilityBulkUploadView.as_view(), name="facility_bulk_upload"),
    path("facilities/<int:pk>/edit/", views.FacilityUpdateView.as_view(), name="facility_update"),
    path("facilities/<int:pk>/delete/", views.FacilityDeleteView.as_view(), name="facility_delete"),
    path("facilities/<int:pk>/", views.FacilityDetailView.as_view(), name="facility_detail"),
    path("users/", views.DashboardUserListView.as_view(), name="user_list"),
    path("users/create/", views.DashboardUserCreateView.as_view(), name="user_create"), 
]
