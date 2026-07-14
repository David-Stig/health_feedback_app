import tempfile
import csv
from io import StringIO

from django.contrib.auth import get_user_model
from django.test import TestCase, override_settings
from django.urls import reverse

from dashboard.models import DashboardUserProfile
from dashboard.views import EXPORT_COLUMNS
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

    def test_feedback_list_paginates_to_ten_responses(self):
        for _ in range(11):
            Feedback.objects.create(
                facility=self.facility_a,
                category=Feedback.Category.WAITING_TIME,
                rating=5,
                gender=Feedback.Gender.FEMALE,
            )

        self.client.login(username="dash", password="secret123")

        response = self.client.get(reverse("dashboard:feedback_list"))

        self.assertEqual(response.status_code, 200)
        self.assertTrue(response.context["is_paginated"])
        self.assertEqual(response.context["paginator"].per_page, 10)
        self.assertEqual(len(response.context["feedback_entries"]), 10)

    def test_dashboard_user_export_is_scoped_to_assigned_facility(self):
        self.client.login(username="dash", password="secret123")

        response = self.client.get(reverse("dashboard:export_csv"))

        self.assertEqual(response.status_code, 200)
        content = response.content.decode("utf-8")
        self.assertIn("Facility A", content)
        self.assertNotIn("Facility B", content)

    def test_dashboard_export_includes_extended_feedback_fields(self):
        Feedback.objects.filter(facility=self.facility_a).update(
            age_group=Feedback.AgeGroup.AGE_25_34,
            distance=Feedback.Distance.LESS_THAN_5KM,
            service=Feedback.Service.OTHER,
            service_other="Mental health consultation",
            difficulty=[Feedback.Difficulty.HEARING, Feedback.Difficulty.MOBILITY],
            received_service=Feedback.receivedService.PARTIALLY,
            reason_not_received=Feedback.ReasonNotReceived.MEDICINE,
            reason_not_received_other="",
            referral=Feedback.Referral.YES,
            facility_type=Feedback.FacilityType.HOSPITAL,
            payment=Feedback.Payment.YES,
            insurance=Feedback.INSURANCE.NONE,
            no_insurance_reason=Feedback.NO_INSURANCE_REASON.CASH,
            cash_payment=Feedback.CASH.BETWEEN,
            cash_payment_other="",
            cost=Feedback.COST.YES,
            medicines=Feedback.MEDICINES.NO_PHARMACY,
            revisit=Feedback.REVISIT.NOT_SURE,
            chance=Feedback.CHANCE.NO,
            reason_not_chance=Feedback.REASON_NOT_CHANCE.FAR,
            reason_not_chance_other="",
            change=Feedback.CHANGE.OTHER,
            change_other="Improve triage",
            aob=Feedback.AOB.YES,
            aob_other="Waiting area needs seating",
        )
        self.client.login(username="dash", password="secret123")

        response = self.client.get(reverse("dashboard:export_csv"))

        rows = list(csv.reader(StringIO(response.content.decode("utf-8"))))
        self.assertEqual(rows[0], [label for label, _getter in EXPORT_COLUMNS])
        self.assertIn("Mental health consultation", rows[1])
        self.assertIn("Hearing (even with hearing aid), Walking or climbing steps", rows[1])
        self.assertIn("Improve triage", rows[1])
        self.assertIn("Waiting area needs seating", rows[1])

    def test_dashboard_home_includes_new_analytics_context(self):
        Feedback.objects.filter(facility=self.facility_a).update(
            received_service=Feedback.receivedService.PARTIALLY,
            payment=Feedback.Payment.YES,
            medicines=Feedback.MEDICINES.NO_PHARMACY,
            revisit=Feedback.REVISIT.YES,
            insurance=Feedback.INSURANCE.NHIMA,
            change=Feedback.CHANGE.MORE_MEDICINES,
            reason_not_received=Feedback.ReasonNotReceived.MEDICINE,
        )
        self.client.login(username="dash", password="secret123")

        response = self.client.get(reverse("dashboard:home"))

        self.assertEqual(response.status_code, 200)
        self.assertIn("received_service_breakdown", response.context)
        self.assertIn("payment_breakdown", response.context)
        self.assertIn("medicines_breakdown", response.context)
        self.assertIn("revisit_breakdown", response.context)
        self.assertIn("insurance_breakdown", response.context)
        self.assertIn("change_breakdown", response.context)
        self.assertIn("reason_not_received_breakdown", response.context)

    def test_dashboard_user_can_open_detail_for_assigned_facility_feedback_only(self):
        visible_feedback = Feedback.objects.filter(facility=self.facility_a).first()
        hidden_feedback = Feedback.objects.filter(facility=self.facility_b).first()
        self.client.login(username="dash", password="secret123")

        visible_response = self.client.get(
            reverse("dashboard:feedback_detail", args=[visible_feedback.pk])
        )
        hidden_response = self.client.get(
            reverse("dashboard:feedback_detail", args=[hidden_feedback.pk])
        )

        self.assertEqual(visible_response.status_code, 200)
        self.assertEqual(visible_response.context["entry"].facility, self.facility_a)
        self.assertEqual(hidden_response.status_code, 404)


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


@override_settings(MEDIA_ROOT=TEST_MEDIA_ROOT)
class DashboardUserManagementTests(TestCase):
    def setUp(self):
        self.staff_user = User.objects.create_user(
            username="staff-admin",
            password="secret123",
            is_staff=True,
        )
        self.dashboard_user = User.objects.create_user(
            username="field-user",
            password="oldpassword123",
        )

    def test_staff_user_can_reset_dashboard_user_password(self):
        self.client.login(username="staff-admin", password="secret123")

        response = self.client.post(
            reverse("dashboard:user_password_reset", args=[self.dashboard_user.pk]),
            data={
                "new_password1": "newsecurepass456",
                "new_password2": "newsecurepass456",
            },
        )

        self.assertRedirects(response, reverse("dashboard:user_list"))
        self.dashboard_user.refresh_from_db()
        self.assertTrue(self.dashboard_user.check_password("newsecurepass456"))

    def test_non_staff_user_cannot_access_password_reset_view(self):
        self.client.login(username="field-user", password="oldpassword123")

        response = self.client.get(
            reverse("dashboard:user_password_reset", args=[self.dashboard_user.pk])
        )

        self.assertEqual(response.status_code, 403)

    def test_staff_user_can_delete_non_admin_user(self):
        self.client.login(username="staff-admin", password="secret123")

        response = self.client.post(
            reverse("dashboard:user_delete", args=[self.dashboard_user.pk])
        )

        self.assertRedirects(response, reverse("dashboard:user_list"))
        self.assertFalse(User.objects.filter(pk=self.dashboard_user.pk).exists())

    def test_staff_user_cannot_delete_admin_account(self):
        self.client.login(username="staff-admin", password="secret123")

        response = self.client.post(
            reverse("dashboard:user_delete", args=[self.staff_user.pk])
        )

        self.assertRedirects(response, reverse("dashboard:user_list"))
        self.assertTrue(User.objects.filter(pk=self.staff_user.pk).exists())
