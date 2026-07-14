from django.urls import path

from . import views

app_name = "facilities"

urlpatterns = [
    path("bulk-regenerate-qr/", views.bulk_regenerate_qr_codes, name="bulk_regenerate_qr"),
    path("<int:pk>/download-qr/", views.download_qr_code, name="download_qr"),
    path("<int:pk>/download-poster/", views.download_feedback_poster, name="download_poster"),
    path("<int:pk>/regenerate-qr/", views.regenerate_qr_code, name="regenerate_qr"),
]
