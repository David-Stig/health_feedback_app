from django.conf import settings
from django.conf.urls.static import static
from django.contrib import admin
from django.contrib.auth import views as auth_views
from django.urls import include, path

from config.forms import DashboardLoginForm
from feedback import views as feedback_views


urlpatterns = [
    path("admin/", admin.site.urls),
    path(
        "",
        auth_views.LoginView.as_view(
            template_name="registration/login.html",
            authentication_form=DashboardLoginForm,
        ),
        name="login",
    ),
    path(
        "accounts/login/",
        auth_views.LoginView.as_view(
            template_name="registration/login.html",
            authentication_form=DashboardLoginForm,
        ),
    ),
    path("accounts/logout/", auth_views.LogoutView.as_view(), name="logout"),
    path("f/<int:facility_id>/", feedback_views.submit_feedback_legacy, name="feedback_short_submit"),
    path("feedback/<int:facility_id>/", feedback_views.submit_feedback_legacy, name="feedback_direct_submit"),
    path("feedback/", include("feedback.urls")),
    path("dashboard/", include("dashboard.urls")),
    path("intelligence/", include("intelligence.urls")),
    path("facilities/", include("facilities.urls")),
]

if settings.DEBUG:
    urlpatterns += static(settings.MEDIA_URL, document_root=settings.MEDIA_ROOT)
