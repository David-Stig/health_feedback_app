import tempfile

from django.core.cache import cache
from django.test import TestCase, override_settings
from django.urls import reverse

from facilities.models import Facility
from feedback.models import Feedback


TEST_MEDIA_ROOT = tempfile.mkdtemp()


@override_settings(
    MEDIA_ROOT=TEST_MEDIA_ROOT,
    RATE_LIMIT_SUBMISSIONS=1,
    RATE_LIMIT_WINDOW_SECONDS=60,
    STATICFILES_STORAGE="django.contrib.staticfiles.storage.StaticFilesStorage",
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
        self.facility_url = reverse("feedback:facility_submit", args=[self.facility.pk])
        self.short_facility_url = reverse("feedback_short_submit", args=[self.facility.pk])

    def _valid_payload(self):
        return {
            "facility": str(self.facility.pk),
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

    def test_submission_persists_all_shared_answers_for_each_rating(self):
        response = self.client.post(self.facility_url, data=self._valid_payload())

        self.assertRedirects(response, reverse("feedback:thank_you"))
        self.assertEqual(Feedback.objects.count(), 2)

        entry = Feedback.objects.get(category=Feedback.Category.WAITING_TIME)
        self.assertEqual(entry.facility, self.facility)
        self.assertEqual(entry.gender, Feedback.Gender.FEMALE)
        self.assertEqual(entry.age_group, Feedback.AgeGroup.AGE_25_34)
        self.assertEqual(entry.distance, Feedback.Distance.LESS_THAN_5KM)
        self.assertEqual(entry.service, Feedback.Service.TREATMENT)
        self.assertEqual(entry.difficulty, [Feedback.Difficulty.NONE])
        self.assertEqual(entry.payment, Feedback.Payment.NO)
        self.assertEqual(entry.comment, "Service was fine.")

    def test_submission_rate_limit_blocks_second_valid_submit(self):
        first_response = self.client.post(self.facility_url, data=self._valid_payload())
        second_response = self.client.post(self.facility_url, data=self._valid_payload())

        self.assertRedirects(first_response, reverse("feedback:thank_you"))
        self.assertEqual(second_response.status_code, 200)
        self.assertContains(second_response, "Too many submissions from this connection")
        self.assertEqual(Feedback.objects.count(), 2)

    def test_submission_with_honeypot_medicine_field_is_rejected(self):
        payload = self._valid_payload()
        payload["medicine"] = "spam bot value"

        response = self.client.post(self.facility_url, data=payload)

        self.assertEqual(response.status_code, 200)
        self.assertIn("medicine", response.context["form"].errors)
        self.assertIn("Spam detected.", response.context["form"].errors["medicine"])
        self.assertEqual(Feedback.objects.count(), 0)

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
        latest_entry = Feedback.objects.filter(comment="Still linked to original facility.").latest("created_at")
        self.assertEqual(latest_entry.facility, self.facility)

    def test_facility_specific_route_locks_selected_facility_on_get(self):
        response = self.client.get(self.facility_url)

        self.assertEqual(response.status_code, 200)
        self.assertEqual(response.context["selected_facility"], self.facility)

    def test_short_facility_route_locks_selected_facility_on_get(self):
        response = self.client.get(self.short_facility_url)

        self.assertEqual(response.status_code, 200)
        self.assertEqual(response.context["selected_facility"], self.facility)
