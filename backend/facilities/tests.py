import tempfile

from django.test import TestCase, override_settings

from .models import Facility


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
            f"https://feedback.example.com/feedback/?facility_id={facility.pk}",
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
            f"https://feedback.example.com/feedback/?facility_id={facility.pk}",
        )
