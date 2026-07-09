import tempfile

from django.contrib.auth import get_user_model
from django.test import TestCase, override_settings
from django.urls import reverse

from .models import Facility

User = get_user_model()

TEST_MEDIA_ROOT = tempfile.mkdtemp()


@override_settings(MEDIA_ROOT=TEST_MEDIA_ROOT, SITE_URL="feedback.example.com")
class FacilityModelTests(TestCase):
    def test_feedback_url_defaults_to_https_when_scheme_is_missing(self):
        facility = Facility.objects.create(
            name="Chawama Clinic",
            district="Lusaka",
            province="Lusaka",
        )

        self.assertEqual(
            facility.get_feedback_url(),
            f"https://feedback.example.com/f/{facility.pk}/",
        )


@override_settings(
    MEDIA_ROOT=TEST_MEDIA_ROOT,
    SITE_URL="http://feedback.example.com",
    SECURE_SSL_REDIRECT=True,
)
class SecureFacilityModelTests(TestCase):
    def test_feedback_url_uses_https_when_ssl_redirect_is_enabled(self):
        facility = Facility.objects.create(
            name="Mtendere Clinic",
            district="Lusaka",
            province="Lusaka",
        )

        self.assertEqual(
            facility.get_feedback_url(),
            f"https://feedback.example.com/f/{facility.pk}/",
        )


@override_settings(MEDIA_ROOT=TEST_MEDIA_ROOT, SITE_URL="feedback.example.com")
class FacilityQrBulkRegenerationTests(TestCase):
    def setUp(self):
        self.staff_user = User.objects.create_user(
            username="staff",
            password="secret123",
            is_staff=True,
        )
        self.facility_a = Facility.objects.create(
            name="A Clinic",
            district="Lusaka",
            province="Lusaka",
        )
        self.facility_b = Facility.objects.create(
            name="B Clinic",
            district="Lusaka",
            province="Lusaka",
        )

    def test_staff_user_can_bulk_regenerate_qr_codes(self):
        self.facility_a.qr_code = ""
        self.facility_a.save(update_fields=["qr_code"])
        self.facility_b.qr_code = ""
        self.facility_b.save(update_fields=["qr_code"])
        self.client.login(username="staff", password="secret123")

        response = self.client.post(reverse("facilities:bulk_regenerate_qr"))

        self.assertRedirects(response, reverse("dashboard:facility_list"))
        self.facility_a.refresh_from_db()
        self.facility_b.refresh_from_db()
        self.assertTrue(self.facility_a.qr_code.name)
        self.assertTrue(self.facility_b.qr_code.name)
