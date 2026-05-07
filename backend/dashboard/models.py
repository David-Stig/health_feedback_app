from django.conf import settings
from django.db import models

from facilities.models import Facility


class DashboardUserProfile(models.Model):
    user = models.OneToOneField(
        settings.AUTH_USER_MODEL,
        on_delete=models.CASCADE,
        related_name="dashboard_profile",
    )
    is_dashboard_user = models.BooleanField(default=True)
    facility = models.ForeignKey(
        Facility,
        on_delete=models.SET_NULL,
        null=True,
        blank=True,
        related_name="dashboard_users",
    )

    class Meta:
        verbose_name = "Dashboard user profile"
        verbose_name_plural = "Dashboard user profiles"

    def __str__(self) -> str:
        return f"{self.user.username} dashboard profile"


def get_or_create_dashboard_profile(user):
    profile, _ = DashboardUserProfile.objects.get_or_create(user=user)
    return profile
