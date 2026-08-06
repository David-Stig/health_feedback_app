from django.urls import path

from intelligence import views

app_name = "intelligence"

urlpatterns = [
    path("", views.IntelligenceDashboardView.as_view(), name="dashboard"),
    path("reports/", views.IntelligenceReportListView.as_view(), name="report_list"),
    path("reports/generate/", views.IntelligenceReportGenerateView.as_view(), name="report_generate"),
    path("reports/weekly/", views.IntelligenceReportListView.as_view(), {"report_type": "weekly"}, name="weekly_reports"),
    path("reports/monthly/", views.IntelligenceReportListView.as_view(), {"report_type": "monthly"}, name="monthly_reports"),
    path("reports/custom/", views.IntelligenceReportListView.as_view(), {"report_type": "custom"}, name="custom_reports"),
    path("reports/facility/", views.IntelligenceReportListView.as_view(), {"report_type": "facility"}, name="facility_reports"),
    path("reports/<int:pk>/", views.IntelligenceReportDetailView.as_view(), name="report_detail"),
    path("reports/<int:pk>/download/pdf/", views.IntelligenceReportPdfDownloadView.as_view(), name="report_download_pdf"),
    path("reports/<int:pk>/regenerate/", views.IntelligenceReportRegenerateView.as_view(), name="report_regenerate"),
    path("reports/<int:pk>/status/<str:action>/", views.IntelligenceReportStatusUpdateView.as_view(), name="report_status"),
    path("facility-intelligence/", views.IntelligenceFacilityListView.as_view(), name="facility_intelligence"),
    path("emerging-issues/", views.IntelligenceIssueListView.as_view(), {"insight_type": "emerging_issue"}, name="emerging_issues"),
    path("recurring-issues/", views.IntelligenceIssueListView.as_view(), {"insight_type": "recurring_issue"}, name="recurring_issues"),
    path("topic-analysis/", views.IntelligenceTopicAnalysisView.as_view(), name="topic_analysis"),
    path("candidate-topics/", views.IntelligenceTopicAnalysisView.as_view(), name="candidate_topics"),
    path("configuration/", views.IntelligenceConfigurationView.as_view(), name="configuration"),
]
