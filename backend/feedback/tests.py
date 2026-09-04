import tempfile
from unittest.mock import patch

from django.core.cache import cache
from django.db import connection
from django.db.migrations.executor import MigrationExecutor
from django.test import TestCase, override_settings
from django.urls import reverse

from facilities.models import Facility
from feedback.consent import CONSENT_VERSION
from feedback.models import Feedback, RatingResponse


TEST_MEDIA_ROOT = tempfile.mkdtemp()


@override_settings(
    MEDIA_ROOT=TEST_MEDIA_ROOT,
    RATE_LIMIT_SUBMISSIONS=1,
    RATE_LIMIT_WINDOW_SECONDS=60,
    STATICFILES_STORAGE="django.contrib.staticfiles.storage.StaticFilesStorage",
    TURNSTILE_ENABLED=False,
    TURNSTILE_SITE_KEY="",
    TURNSTILE_SECRET_KEY="",
)
class FeedbackSubmissionTests(TestCase):
    def setUp(self):
        cache.clear()
        self.facility = Facility.objects.create(
            name="Chilenje Clinic",
            district="Lusaka",
            province="Lusaka",
        )
        self.url = reverse("feedback:submit")
        self.facility_url = reverse(
            "feedback:facility_submit",
            kwargs={
                "facility_slug": self.facility.get_feedback_slug(),
                "facility_id": self.facility.pk,
            },
        )
        self.short_facility_url = reverse("feedback_short_submit", args=[self.facility.pk])
        self.legacy_facility_url = reverse("feedback:facility_submit_legacy", args=[self.facility.pk])

    def _valid_payload(self):
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
            f"comment_{Feedback.Category.WAITING_TIME}": "Service was fine.",
            f"rating_{Feedback.Category.CLEANLINESS}": "5",
            f"comment_{Feedback.Category.CLEANLINESS}": "Very clean.",
        }

    def test_submission_creates_one_parent_submission_with_multiple_rating_responses(self):
        response = self.client.post(self.facility_url, data=self._valid_payload())

        self.assertRedirects(response, reverse("feedback:thank_you"))
        self.assertEqual(Feedback.objects.count(), 1)
        self.assertEqual(RatingResponse.objects.count(), 2)

        entry = Feedback.objects.get()
        self.assertEqual(entry.facility, self.facility)
        self.assertEqual(entry.gender, Feedback.Gender.FEMALE)
        self.assertEqual(entry.age_group, Feedback.AgeGroup.AGE_25_34)
        self.assertEqual(entry.distance, Feedback.Distance.LESS_THAN_5KM)
        self.assertEqual(entry.service, Feedback.Service.TREATMENT)
        self.assertEqual(entry.difficulty, [Feedback.Difficulty.NONE])
        self.assertEqual(entry.payment, Feedback.Payment.NO)
        self.assertEqual(entry.rating_response_count, 2)
        self.assertIs(entry.consent_acknowledged, True)
        self.assertEqual(entry.consent_version, CONSENT_VERSION)
        self.assertTrue(
            entry.rating_responses.filter(
                category=Feedback.Category.WAITING_TIME,
                rating=4,
                comment="Service was fine.",
            ).exists()
        )

    def test_submission_rate_limit_blocks_second_valid_submit(self):
        first_response = self.client.post(self.facility_url, data=self._valid_payload())
        second_response = self.client.post(self.facility_url, data=self._valid_payload())

        self.assertRedirects(first_response, reverse("feedback:thank_you"))
        self.assertEqual(second_response.status_code, 200)
        self.assertContains(second_response, "Too many submissions from this connection")
        self.assertEqual(Feedback.objects.count(), 1)
        self.assertEqual(RatingResponse.objects.count(), 2)

    def test_submission_with_honeypot_medicine_field_is_rejected(self):
        payload = self._valid_payload()
        payload["medicine"] = "spam bot value"

        response = self.client.post(self.facility_url, data=payload)

        self.assertEqual(response.status_code, 200)
        self.assertIn("medicine", response.context["form"].errors)
        self.assertIn("Spam detected.", response.context["form"].errors["medicine"])
        self.assertEqual(Feedback.objects.count(), 0)

    def test_submission_without_consent_is_rejected(self):
        payload = self._valid_payload()
        payload.pop("consent_acknowledged", None)

        response = self.client.post(self.facility_url, data=payload)

        self.assertEqual(response.status_code, 200)
        self.assertIn("consent_acknowledged", response.context["form"].errors)
        self.assertContains(
            response,
            "Please confirm that you agree to participate before submitting your feedback.",
        )
        self.assertEqual(Feedback.objects.count(), 0)
        self.assertEqual(RatingResponse.objects.count(), 0)

    @patch("feedback.views.verify_turnstile", return_value=(True, None))
    def test_backend_bypass_without_consent_is_rejected_before_turnstile(self, mocked_verify_turnstile):
        payload = self._valid_payload()
        payload.pop("consent_acknowledged", None)

        response = self.client.post(self.facility_url, data=payload)

        self.assertEqual(response.status_code, 200)
        self.assertIn("consent_acknowledged", response.context["form"].errors)
        self.assertEqual(Feedback.objects.count(), 0)
        self.assertEqual(RatingResponse.objects.count(), 0)
        mocked_verify_turnstile.assert_not_called()

    def test_invalid_questionnaire_with_consent_preserves_submission_block(self):
        payload = self._valid_payload()
        payload["received_service"] = Feedback.receivedService.NO
        payload["reason_not_received"] = ""

        response = self.client.post(self.facility_url, data=payload)

        self.assertEqual(response.status_code, 200)
        self.assertIn("reason_not_received", response.context["form"].errors)
        self.assertEqual(Feedback.objects.count(), 0)
        self.assertEqual(RatingResponse.objects.count(), 0)

    def test_submit_another_response_keeps_same_facility_locked(self):
        self.client.post(self.facility_url, data=self._valid_payload())

        response = self.client.get(self.url)

        self.assertEqual(response.status_code, 200)
        self.assertEqual(response.context["selected_facility"], self.facility)
        self.assertQuerySetEqual(
            response.context["form"].fields["facility"].queryset.order_by("pk"),
            [self.facility],
            transform=lambda facility: facility,
        )

    def test_locked_facility_cannot_be_switched_by_posting_another_facility(self):
        other_facility = Facility.objects.create(
            name="Matero Clinic",
            district="Lusaka",
            province="Lusaka",
        )

        self.client.post(self.facility_url, data=self._valid_payload())
        cache.clear()
        payload = self._valid_payload()
        payload["facility"] = str(other_facility.pk)
        payload[f"comment_{Feedback.Category.WAITING_TIME}"] = "Still linked to original facility."

        response = self.client.post(self.url, data=payload)

        self.assertRedirects(response, reverse("feedback:thank_you"))
        latest_entry = Feedback.objects.latest("created_at")
        self.assertEqual(latest_entry.facility, self.facility)
        self.assertTrue(
            latest_entry.rating_responses.filter(comment="Still linked to original facility.").exists()
        )

    def test_facility_specific_route_locks_selected_facility_on_get(self):
        response = self.client.get(self.facility_url)

        self.assertEqual(response.status_code, 200)
        self.assertEqual(response.context["selected_facility"], self.facility)

    def test_short_facility_route_locks_selected_facility_on_get(self):
        response = self.client.get(self.short_facility_url)

        self.assertRedirects(response, self.facility_url)

    def test_legacy_facility_route_redirects_to_slug_url(self):
        response = self.client.get(self.legacy_facility_url)

        self.assertRedirects(response, self.facility_url)

    def test_slug_facility_route_locks_selected_facility_on_get(self):
        response = self.client.get(self.facility_url)

        self.assertEqual(response.status_code, 200)
        self.assertEqual(response.context["selected_facility"], self.facility)

    @override_settings(TURNSTILE_ENABLED=True, TURNSTILE_SITE_KEY="site-key", TURNSTILE_SECRET_KEY="secret-key")
    def test_submission_requires_turnstile_when_enabled(self):
        response = self.client.post(self.facility_url, data=self._valid_payload())

        self.assertEqual(response.status_code, 200)
        self.assertContains(response, "Please complete the security check.")
        self.assertEqual(Feedback.objects.count(), 0)

    @override_settings(TURNSTILE_ENABLED=False, TURNSTILE_SITE_KEY="", TURNSTILE_SECRET_KEY="")
    def test_local_submission_bypasses_turnstile_when_disabled(self):
        response = self.client.post(self.facility_url, data=self._valid_payload())

        self.assertRedirects(response, reverse("feedback:thank_you"))
        self.assertEqual(Feedback.objects.count(), 1)

    @override_settings(TURNSTILE_ENABLED=True, TURNSTILE_SITE_KEY="site-key", TURNSTILE_SECRET_KEY="secret-key")
    @patch("feedback.views.verify_turnstile", return_value=(True, None))
    def test_submission_succeeds_when_turnstile_verification_passes(self, mocked_verify_turnstile):
        payload = self._valid_payload()
        payload["cf-turnstile-response"] = "token-value"

        response = self.client.post(self.facility_url, data=payload)

        self.assertRedirects(response, reverse("feedback:thank_you"))
        self.assertEqual(Feedback.objects.count(), 1)
        self.assertEqual(RatingResponse.objects.count(), 2)
        mocked_verify_turnstile.assert_called_once()

    def test_historical_feedback_defaults_to_unknown_consent_status(self):
        entry = Feedback.objects.create(facility=self.facility)

        self.assertIsNone(entry.consent_acknowledged)
        self.assertIsNone(entry.consent_version)

    def test_public_form_shows_18_24_and_not_15_24(self):
        response = self.client.get(self.facility_url)

        self.assertEqual(response.status_code, 200)
        self.assertContains(response, "18-24 years")
        self.assertNotContains(response, "15-24 years")

    def test_public_form_shows_new_no_insurance_reason_option_in_correct_order(self):
        response = self.client.get(self.facility_url)

        self.assertEqual(response.status_code, 200)
        choices = [value for value, _label in response.context["form"].fields["no_insurance_reason"].choices]
        new_option = Feedback.NO_INSURANCE_REASON.NOT_NEEDED
        previous_option = Feedback.NO_INSURANCE_REASON.DID_NOT_HAVE
        next_option = Feedback.NO_INSURANCE_REASON.CASH
        self.assertIn(new_option, choices)
        self.assertLess(choices.index(previous_option), choices.index(new_option))
        self.assertLess(choices.index(new_option), choices.index(next_option))
        self.assertEqual(choices.count(new_option), 1)

    def test_submission_accepts_new_no_insurance_reason_option(self):
        payload = self._valid_payload()
        payload["insurance"] = Feedback.INSURANCE.NONE
        payload["no_insurance_reason"] = Feedback.NO_INSURANCE_REASON.NOT_NEEDED

        response = self.client.post(self.facility_url, data=payload)

        self.assertRedirects(response, reverse("feedback:thank_you"))
        entry = Feedback.objects.get()
        self.assertEqual(entry.no_insurance_reason, Feedback.NO_INSURANCE_REASON.NOT_NEEDED)
        self.assertEqual(entry.no_insurance_reason_other, "")


class AgeGroupMigrationTests(TestCase):
    migrate_from = [("feedback", "0017_feedback_consent_acknowledged_and_more")]
    migrate_to = [("feedback", "0018_update_age_group_15_24_to_18_24")]

    def setUp(self):
        super().setUp()
        self.executor = MigrationExecutor(connection)
        self.executor.migrate(self.migrate_from)
        old_apps = self.executor.loader.project_state(self.migrate_from).apps
        Facility = old_apps.get_model("facilities", "Facility")
        Feedback = old_apps.get_model("feedback", "Feedback")
        facility = Facility.objects.create(name="Legacy Facility", district="Lusaka", province="Lusaka")
        Feedback.objects.create(
            facility_id=facility.pk,
            age_group="15-24 years",
            submitted_on="2026-08-19",
        )
        self.executor = MigrationExecutor(connection)
        self.executor.migrate(self.migrate_to)

    def test_historical_15_24_rows_are_migrated_to_18_24(self):
        Feedback = self.executor.loader.project_state(self.migrate_to).apps.get_model("feedback", "Feedback")

        self.assertEqual(Feedback.objects.filter(age_group="15-24 years").count(), 0)
        self.assertEqual(Feedback.objects.filter(age_group="18-24 years").count(), 1)
