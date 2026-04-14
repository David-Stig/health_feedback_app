from django.urls import path

from . import views

app_name = "facilities"

urlpatterns = [
    path("<int:pk>/download-qr/", views.download_qr_code, name="download_qr"),
]
