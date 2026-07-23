from django.contrib.auth.mixins import LoginRequiredMixin, UserPassesTestMixin
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


def accessible_facilities_for_user(user):
    from facilities.models import Facility

    queryset = Facility.objects.all()
    if not user.is_authenticated:
        return queryset.none()
    if user.is_staff:
        return queryset

    profile = get_or_create_dashboard_profile(user)
    if profile.is_dashboard_user and profile.facility_id:
        return queryset.filter(pk=profile.facility_id)
    return queryset.none()


class PermissionOrStaffRequiredMixin(DashboardAccessMixin):
    permission_required = ""

    def has_required_permission(self):
        user = self.request.user
        if not user.is_authenticated:
            return False
        if user.is_staff:
            return True
        return bool(self.permission_required and user.has_perm(self.permission_required))

    def test_func(self):
        return super().test_func() and self.has_required_permission()


class StaffRequiredMixin(DashboardAccessMixin):
    login_url = "/"  # ✅ redirect unauthenticated users to homepage login

    def test_func(self):
        return self.request.user.is_staff

    def handle_no_permission(self):
        if not self.request.user.is_authenticated:
            return super().handle_no_permission()
        raise PermissionDenied  # ✅ logged in but not staff → 403
