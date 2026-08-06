import tempfile

from django.contrib.auth import get_user_model
from django.test import TestCase, override_settings
from django.urls import reverse
from django.utils import timezone

from facilities.models import Facility
from feedback.models import Feedback, RatingResponse
from intelligence.models import IntelligenceReport
from intelligence.services.report_generation_service import generate_intelligence_report

User = get_user_model()
TEST_MEDIA_ROOT = tempfile.mkdtemp()


@override_settings(MEDIA_ROOT=TEST_MEDIA_ROOT)
class IntelligenceModuleTests(TestCase):
    def setUp(self):
        self.staff_user = User.objects.create_user(
            username="staff",
            password="secret123",
            is_staff=True,
        )
        self.facility = Facility.objects.create(name="Facility A", district="A", province="P1")
        submission = Feedback.objects.create(
            facility=self.facility,
            insurance=Feedback.INSURANCE.NHIMA,
            medicines=Feedback.MEDICINES.NO_PHARMACY,
            change=Feedback.CHANGE.MORE_MEDICINES,
            comment="Medicines were unavailable and waiting was too long.",
        )
        RatingResponse.objects.bulk_create(
            [
                RatingResponse(
                    submission=submission,
                    category=Feedback.Category.WAITING_TIME,
                    rating=2,
                    comment="The queue was long.",
                ),
                RatingResponse(
                    submission=submission,
                    category=Feedback.Category.MEDICATION,
                    rating=1,
                    comment="Medicines were not in stock.",
                ),
            ]
        )

    def test_generate_intelligence_report_creates_report_version_and_insights(self):
        report = generate_intelligence_report(
            user=self.staff_user,
            report_type=IntelligenceReport.ReportType.WEEKLY,
        )

        self.assertTrue(report.report_code.startswith("WIR-"))
        self.assertEqual(report.version, 1)
        self.assertEqual(report.versions.count(), 1)
        self.assertGreater(report.insights.count(), 0)
        self.assertIn("submissions", report.executive_summary.lower())

    def test_regenerating_draft_creates_new_version_without_losing_old_versions(self):
        report = generate_intelligence_report(
            user=self.staff_user,
            report_type=IntelligenceReport.ReportType.WEEKLY,
        )
        first_version_count = report.versions.count()

        regenerate_intelligence = generate_intelligence_report(
            user=self.staff_user,
            report_type=report.report_type,
            period_start=report.period_start,
            period_end=report.period_end,
            report=report,
        )

        self.assertEqual(regenerate_intelligence.version, 2)
        self.assertEqual(regenerate_intelligence.versions.count(), first_version_count + 1)

    def test_dashboard_and_generation_views_are_available_to_staff(self):
        self.client.login(username="staff", password="secret123")

        dashboard_response = self.client.get(reverse("intelligence:dashboard"))
        generate_response = self.client.post(
            reverse("intelligence:report_generate"),
            {
                "report_type": IntelligenceReport.ReportType.WEEKLY,
                "period_start": timezone.localdate(),
                "period_end": timezone.localdate(),
            },
        )

        self.assertEqual(dashboard_response.status_code, 200)
        self.assertEqual(generate_response.status_code, 302)
        self.assertEqual(IntelligenceReport.objects.count(), 1)

    def test_report_pdf_download_returns_attachment(self):
        report = generate_intelligence_report(
            user=self.staff_user,
            report_type=IntelligenceReport.ReportType.WEEKLY,
        )
        self.client.login(username="staff", password="secret123")

        response = self.client.get(reverse("intelligence:report_download_pdf", args=[report.pk]))

        self.assertEqual(response.status_code, 200)
        self.assertEqual(response["Content-Type"], "application/pdf")
        self.assertIn(".pdf", response["Content-Disposition"])
        pdf_bytes = b"".join(response.streaming_content)
        self.assertIn(b"Key Insights", pdf_bytes)
        self.assertNotIn(b"Supporting Evidence", pdf_bytes)

    def test_approved_report_cannot_be_regenerated(self):
        report = generate_intelligence_report(
            user=self.staff_user,
            report_type=IntelligenceReport.ReportType.WEEKLY,
        )
        report.status = IntelligenceReport.Status.APPROVED
        report.save(update_fields=["status"])

        with self.assertRaisesMessage(ValueError, "Approved reports cannot be regenerated."):
            generate_intelligence_report(
                user=self.staff_user,
                report_type=report.report_type,
                period_start=report.period_start,
                period_end=report.period_end,
                report=report,
            )
