from django.urls import path

from . import views
from . import bulk_views

app_name = "dashboard"

urlpatterns = [
    path("", views.DashboardHomeView.as_view(), name="home"),
    path("account/", views.DashboardAccountView.as_view(), name="account"),
    path("feedback/", views.FeedbackListView.as_view(), name="feedback_list"),
    path("feedback/<int:pk>/", views.FeedbackDetailView.as_view(), name="feedback_detail"),
    path("feedback/export/csv/", views.export_feedback_csv, name="export_csv"),
    path("feedback/export/excel/", views.export_feedback_excel, name="export_excel"),
    path("bulk/sessions/", bulk_views.CollectionSessionListView.as_view(), name="bulk_session_list"),
    path("bulk/sessions/new/", bulk_views.CollectionSessionCreateView.as_view(), name="bulk_session_create"),
    path("bulk/sessions/<int:pk>/", bulk_views.CollectionSessionDetailView.as_view(), name="bulk_session_detail"),
    path("bulk/sessions/<int:pk>/delete/", bulk_views.CollectionSessionDeleteView.as_view(), name="bulk_session_delete"),
    path("bulk/sessions/<int:pk>/capture/", bulk_views.AssistedCaptureView.as_view(), name="bulk_session_capture"),
    path("bulk/sessions/<int:pk>/<str:action>/", bulk_views.CollectionSessionStatusUpdateView.as_view(), name="bulk_session_status"),
    path("bulk/imports/", bulk_views.SpreadsheetImportsDisabledView.as_view(), name="bulk_import_list"),
    path("bulk/imports/template/", bulk_views.SpreadsheetImportsDisabledView.as_view(), name="bulk_import_template"),
    path("bulk/imports/upload/", bulk_views.SpreadsheetImportsDisabledView.as_view(), name="bulk_import_upload"),
    path("bulk/imports/<int:pk>/", bulk_views.SpreadsheetImportsDisabledView.as_view(), name="bulk_import_detail"),
    path("bulk/imports/<int:pk>/confirm/", bulk_views.SpreadsheetImportsDisabledView.as_view(), name="bulk_import_confirm"),
    path("bulk/imports/<int:pk>/errors/", bulk_views.SpreadsheetImportsDisabledView.as_view(), name="bulk_import_errors"),
    path("bulk/imports/<int:pk>/rollback/", bulk_views.SpreadsheetImportsDisabledView.as_view(), name="bulk_import_rollback"),
    path("facilities/", views.FacilityListView.as_view(), name="facility_list"),
    path("facilities/new/", views.FacilityCreateView.as_view(), name="facility_create"),
    path("facilities/upload/", views.FacilityBulkUploadView.as_view(), name="facility_bulk_upload"),
    path("facilities/<int:pk>/edit/", views.FacilityUpdateView.as_view(), name="facility_update"),
    path("facilities/<int:pk>/delete/", views.FacilityDeleteView.as_view(), name="facility_delete"),
    path("facilities/<int:pk>/", views.FacilityDetailView.as_view(), name="facility_detail"),
    path("users/", views.DashboardUserListView.as_view(), name="user_list"),
    path("users/create/", views.DashboardUserCreateView.as_view(), name="user_create"),
    path("users/<int:pk>/edit/", views.DashboardUserUpdateView.as_view(), name="user_update"),
    path("users/<int:pk>/reset-password/", views.DashboardUserPasswordResetView.as_view(), name="user_password_reset"),
    path("users/<int:pk>/delete/", views.DashboardUserDeleteView.as_view(), name="user_delete"),
]
