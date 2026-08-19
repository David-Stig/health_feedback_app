import tempfile
from io import BytesIO

from django.contrib.auth import get_user_model
from django.test import TestCase, override_settings
from django.urls import reverse

from dashboard.models import DashboardUserProfile
from facilities.models import Facility
from feedback.consent import CONSENT_VERSION
from feedback.models import CollectionSession, Feedback, RatingResponse

User = get_user_model()
TEST_MEDIA_ROOT = tempfile.mkdtemp()


@override_settings(
    MEDIA_ROOT=TEST_MEDIA_ROOT,
    STATICFILES_STORAGE="django.contrib.staticfiles.storage.StaticFilesStorage",
)
class BulkWorkflowTests(TestCase):
    def setUp(self):
        self.staff_user = User.objects.create_user(
            username="bulk-admin",
            password="secret123",
            is_staff=True,
        )
        self.dashboard_user = User.objects.create_user(
            username="bulk-field",
            password="secret123",
        )
        self.facility = Facility.objects.create(
            name="Kanyama Level One Hospital",
            district="Lusaka",
            province="Lusaka",
        )
        profile = DashboardUserProfile.objects.get(user=self.dashboard_user)
        profile.is_dashboard_user = True
        profile.facility = self.facility
        profile.save()

    def _assisted_payload(self):
        return {
            "facility": str(self.facility.pk),
            "consent_acknowledged": "on",
            "gender": Feedback.Gender.FEMALE,
            "age_group": Feedback.AgeGroup.AGE_25_34,
            "distance": Feedback.Distance.LESS_THAN_5KM,
            "service": Feedback.Service.TREATMENT,
            "difficulty": [Feedback.Difficulty.NONE],
            "received_service": Feedback.receivedService.YES,
            "referral": Feedback.Referral.NO,
            "payment": Feedback.Payment.NO,
            "insurance": Feedback.INSURANCE.NONE,
            "no_insurance_reason": Feedback.NO_INSURANCE_REASON.NONE,
            "cost": Feedback.COST.NO,
            "medicines": Feedback.MEDICINES.YES,
            "revisit": Feedback.REVISIT.YES,
            "chance": Feedback.CHANCE.YES,
            "change": Feedback.CHANGE.MORE_MEDICINES,
            "aob": Feedback.AOB.NO,
            f"rating_{Feedback.Category.WAITING_TIME}": "4",
            f"comment_{Feedback.Category.WAITING_TIME}": "Captured in outreach.",
        }

    def _session(self, status=CollectionSession.Status.ACTIVE):
        return CollectionSession.objects.create(
            facility=self.facility,
            campaign_name="Urban outreach",
            programme_name="Adolescent health",
            collection_method="Tablet assisted",
            collected_by=self.staff_user,
            status=status,
        )

    def test_staff_user_can_create_collection_session(self):
        self.client.login(username="bulk-admin", password="secret123")

        response = self.client.post(
            reverse("dashboard:bulk_session_create"),
            data={
                "facility": str(self.facility.pk),
                "campaign_name": "Market outreach",
                "programme_name": "UHC campaign",
                "collection_method": "Enumerator interview",
                "start_date": "2026-07-22",
                "location": "Kanyama market",
                "notes": "Morning shift",
            },
        )

        self.assertRedirects(response, reverse("dashboard:bulk_session_list"))
        session = CollectionSession.objects.get(campaign_name="Market outreach")
        self.assertTrue(session.session_code.startswith("CS-2026-"))

    def test_dashboard_user_cannot_create_session_for_inaccessible_facility(self):
        other_facility = Facility.objects.create(
            name="Mansa General Hospital",
            district="Mansa",
            province="Luapula",
        )
        self.client.login(username="bulk-field", password="secret123")

        response = self.client.post(
            reverse("dashboard:bulk_session_create"),
            data={
                "facility": str(other_facility.pk),
                "campaign_name": "Blocked outreach",
                "programme_name": "",
                "collection_method": "Enumerator interview",
                "start_date": "2026-07-22",
            },
        )

        self.assertEqual(response.status_code, 403)

    def test_active_session_capture_creates_assisted_feedback(self):
        session = self._session()
        self.client.login(username="bulk-admin", password="secret123")

        response = self.client.post(
            reverse("dashboard:bulk_session_capture", args=[session.pk]),
            data={**self._assisted_payload(), "capture_action": "next"},
        )

        self.assertRedirects(response, reverse("dashboard:bulk_session_capture", args=[session.pk]))
        entry = Feedback.objects.get()
        self.assertEqual(entry.submission_source, Feedback.SubmissionSource.ASSISTED_CAPTURE)
        self.assertEqual(entry.collection_session, session)
        self.assertEqual(entry.captured_by, self.staff_user)
        self.assertIs(entry.consent_acknowledged, True)
        self.assertEqual(entry.consent_version, CONSENT_VERSION)
        self.assertEqual(entry.rating_response_count, 1)
        self.assertTrue(
            RatingResponse.objects.filter(
                submission=entry,
                category=Feedback.Category.WAITING_TIME,
                rating=4,
                comment="Captured in outreach.",
            ).exists()
        )

    def test_active_session_capture_requires_consent(self):
        session = self._session()
        self.client.login(username="bulk-admin", password="secret123")
        payload = self._assisted_payload()
        payload.pop("consent_acknowledged", None)

        response = self.client.post(
            reverse("dashboard:bulk_session_capture", args=[session.pk]),
            data={**payload, "capture_action": "next"},
        )

        self.assertEqual(response.status_code, 200)
        self.assertContains(
            response,
            "Please confirm that you agree to participate before submitting your feedback.",
        )
        self.assertEqual(Feedback.objects.count(), 0)
        self.assertEqual(RatingResponse.objects.count(), 0)

    def test_assisted_capture_includes_new_no_insurance_reason_option(self):
        session = self._session()
        self.client.login(username="bulk-admin", password="secret123")

        response = self.client.get(reverse("dashboard:bulk_session_capture", args=[session.pk]))

        self.assertEqual(response.status_code, 200)
        content = response.content.decode("utf-8")
        self.assertIn("I have health insurance, but I did not need to use it", content)

    def test_assisted_capture_accepts_new_no_insurance_reason_option(self):
        session = self._session()
        self.client.login(username="bulk-admin", password="secret123")
        payload = self._assisted_payload()
        payload["insurance"] = Feedback.INSURANCE.NONE
        payload["no_insurance_reason"] = Feedback.NO_INSURANCE_REASON.NOT_NEEDED

        response = self.client.post(
            reverse("dashboard:bulk_session_capture", args=[session.pk]),
            data={**payload, "capture_action": "next"},
        )

        self.assertRedirects(response, reverse("dashboard:bulk_session_capture", args=[session.pk]))
        entry = Feedback.objects.get()
        self.assertEqual(entry.no_insurance_reason, Feedback.NO_INSURANCE_REASON.NOT_NEEDED)
        self.assertEqual(entry.no_insurance_reason_other, "")

    def test_paused_session_does_not_accept_new_responses(self):
        session = self._session(status=CollectionSession.Status.PAUSED)
        self.client.login(username="bulk-admin", password="secret123")

        response = self.client.get(reverse("dashboard:bulk_session_capture", args=[session.pk]))

        self.assertRedirects(response, reverse("dashboard:bulk_session_detail", args=[session.pk]))

    def test_staff_user_can_delete_collection_session(self):
        session = self._session()
        self.client.login(username="bulk-admin", password="secret123")

        response = self.client.post(reverse("dashboard:bulk_session_delete", args=[session.pk]))

        self.assertRedirects(response, reverse("dashboard:bulk_session_list"))
        self.assertFalse(CollectionSession.objects.filter(pk=session.pk).exists())

    def test_spreadsheet_import_routes_redirect_while_disabled(self):
        self.client.login(username="bulk-admin", password="secret123")

        response = self.client.get(reverse("dashboard:bulk_import_template"), follow=True)

        self.assertRedirects(response, reverse("dashboard:bulk_session_list"))
        messages = list(response.context["messages"])
        self.assertTrue(any("temporarily disabled" in str(message) for message in messages))
