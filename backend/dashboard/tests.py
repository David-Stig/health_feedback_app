import tempfile

from django.contrib.auth import get_user_model
from django.test import TestCase, override_settings
from django.urls import reverse

from dashboard.models import DashboardUserProfile
from facilities.forms import FacilityForm
from facilities.models import Facility
from feedback.models import Feedback

User = get_user_model()
TEST_MEDIA_ROOT = tempfile.mkdtemp()


@override_settings(MEDIA_ROOT=TEST_MEDIA_ROOT)
class DashboardAccessTests(TestCase):
    def setUp(self):
        self.facility_a = Facility.objects.create(name="Facility A", district="A", province="P1")
        self.facility_b = Facility.objects.create(name="Facility B", district="B", province="P2")
        self.dashboard_user = User.objects.create_user(username="dash", password="secret123")
        profile = DashboardUserProfile.objects.get(user=self.dashboard_user)
        profile.is_dashboard_user = True
        profile.facility = self.facility_a
        profile.save()

        Feedback.objects.create(
            facility=self.facility_a,
            category=Feedback.Category.WAITING_TIME,
            rating=4,
            gender=Feedback.Gender.FEMALE,
        )
        Feedback.objects.create(
            facility=self.facility_b,
            category=Feedback.Category.CLEANLINESS,
            rating=2,
            gender=Feedback.Gender.MALE,
        )

    def test_dashboard_user_only_sees_assigned_facility_feedback(self):
        self.client.login(username="dash", password="secret123")

        response = self.client.get(reverse("dashboard:feedback_list"))

        returned_facilities = {
            entry.facility.name for entry in response.context["feedback_entries"]
        }
        self.assertEqual(returned_facilities, {"Facility A"})

    def test_dashboard_user_export_is_scoped_to_assigned_facility(self):
        self.client.login(username="dash", password="secret123")

        response = self.client.get(reverse("dashboard:export_csv"))

        self.assertEqual(response.status_code, 200)
        content = response.content.decode("utf-8")
        self.assertIn("Facility A", content)
        self.assertNotIn("Facility B", content)


@override_settings(MEDIA_ROOT=TEST_MEDIA_ROOT)
class FacilityManagementTests(TestCase):
    def setUp(self):
        self.staff_user = User.objects.create_user(
            username="staff",
            password="secret123",
            is_staff=True,
        )
        self.facility = Facility.objects.create(
            name="Delete Me Clinic",
            district="Lusaka",
            province="Lusaka",
        )

    def test_staff_user_can_delete_facility_from_dashboard(self):
        self.client.login(username="staff", password="secret123")

        response = self.client.post(reverse("dashboard:facility_delete", args=[self.facility.pk]))

        self.assertRedirects(response, reverse("dashboard:facility_list"))
        self.assertFalse(Facility.objects.filter(pk=self.facility.pk).exists())

    def test_facility_form_rejects_district_not_in_selected_province(self):
        form = FacilityForm(
            data={
                "name": "Mismatch Clinic",
                "province": "Lusaka",
                "district": "Kitwe",
            }
        )

        self.assertFalse(form.is_valid())
        self.assertIn("district", form.errors)
