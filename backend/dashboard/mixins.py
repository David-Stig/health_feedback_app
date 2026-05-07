from django.contrib.auth.mixins import LoginRequiredMixin, UserPassesTestMixin
from django.core.exceptions import PermissionDenied
from django.core.exceptions import PermissionDenied

from .models import get_or_create_dashboard_profile


class DashboardAccessMixin(LoginRequiredMixin, UserPassesTestMixin):
    login_url = "login"

    def test_func(self):
        user = self.request.user
        if not user.is_authenticated:
            return False
        if user.is_staff:
            return True
        profile = get_or_create_dashboard_profile(user)
        return profile.is_dashboard_user

    def handle_no_permission(self):
        if not self.request.user.is_authenticated:
            return super().handle_no_permission()
        raise PermissionDenied


class StaffRequiredMixin(DashboardAccessMixin):
    login_url = "/"  # ✅ redirect unauthenticated users to homepage login

    def test_func(self):
        return self.request.user.is_staff

    def handle_no_permission(self):
        if not self.request.user.is_authenticated:
            return super().handle_no_permission()
        raise PermissionDenied  # ✅ logged in but not staff → 403
