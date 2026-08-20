import tempfile

from django.contrib.auth import get_user_model
from django.test import TestCase, override_settings
from django.urls import reverse


User = get_user_model()
TEST_MEDIA_ROOT = tempfile.mkdtemp()


@override_settings(
    MEDIA_ROOT=TEST_MEDIA_ROOT,
    STATICFILES_STORAGE="django.contrib.staticfiles.storage.StaticFilesStorage",
)
class LoginPageTests(TestCase):
    def setUp(self):
        self.user = User.objects.create_user(username="adminuser", password="secret123")

    def test_login_page_renders_clean_compact_content(self):
        response = self.client.get(reverse("login"))

        self.assertEqual(response.status_code, 200)
        self.assertContains(response, "Admin Login")
        self.assertContains(response, "Health Facility Feedback System")
        self.assertContains(response, "Centre for Reproductive Health and Education")
        self.assertContains(response, 'src="/static/images/CRHE_logo.png"', html=False)
        self.assertContains(response, 'alt="Centre for Reproductive Health and Education logo"', html=False)
        self.assertContains(response, 'name="csrfmiddlewaretoken"', html=False)
        self.assertContains(response, 'name="username"', html=False)
        self.assertContains(response, 'autocomplete="username"', html=False)
        self.assertContains(response, 'name="password"', html=False)
        self.assertContains(response, 'autocomplete="current-password"', html=False)
        self.assertContains(response, 'type="submit"', html=False)
        self.assertContains(response, ">Sign in<", html=False)
        self.assertContains(response, 'data-password-toggle', html=False)
        self.assertContains(response, 'aria-label="Show password"', html=False)
        self.assertNotContains(response, "SECURE DASHBOARD")
        self.assertNotContains(response, "Secure Dashboard")
        self.assertNotContains(
            response,
            "Use your staff account to manage facilities, review submissions, and export reports.",
        )
        self.assertNotContains(response, "Admin sign in")

    def test_invalid_credentials_are_rejected_with_generic_error(self):
        response = self.client.post(
            reverse("login"),
            data={"username": "adminuser", "password": "wrongpass"},
        )

        self.assertEqual(response.status_code, 200)
        self.assertFalse(response.wsgi_request.user.is_authenticated)
        self.assertContains(
            response,
            "Please enter a correct username and password. Note that both fields may be case-sensitive.",
        )
        self.assertContains(response, 'value="adminuser"', html=False)

    def test_valid_credentials_still_authenticate(self):
        response = self.client.post(
            reverse("login"),
            data={"username": "adminuser", "password": "secret123"},
        )

        self.assertEqual(response.status_code, 302)
        self.assertEqual(response.headers["Location"], reverse("dashboard:home"))
