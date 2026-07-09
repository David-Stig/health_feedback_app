from django.db import models
from django.core.files.base import ContentFile
from django.urls import reverse
from django.conf import settings
from django.utils.text import slugify
from io import BytesIO
from urllib.parse import urlsplit, urlunsplit


class Facility(models.Model):
    name = models.CharField(max_length=255)
    district = models.CharField(max_length=120)
    province = models.CharField(max_length=120)
    qr_code = models.ImageField(upload_to="qrcodes/", blank=True)
    created_at = models.DateTimeField(auto_now_add=True)

    class Meta:
        ordering = ["province", "district", "name"]

    def __str__(self) -> str:
        return f"{self.name} ({self.district})"

    def _normalized_site_url(self) -> str:
        raw_site_url = (getattr(settings, "SITE_URL", "") or "").strip()
        if not raw_site_url:
            raise ValueError("SITE_URL must be configured to generate QR codes.")

        if "://" not in raw_site_url:
            raw_site_url = f"https://{raw_site_url}"

        parsed = urlsplit(raw_site_url)
        scheme = parsed.scheme or "https"
        netloc = parsed.netloc
        site_port = (getattr(settings, "SITE_PORT", "") or "").strip()

        if getattr(settings, "SECURE_SSL_REDIRECT", False):
            scheme = "https"

        if site_port and ":" not in netloc:
            netloc = f"{netloc}:{site_port}"

        return urlunsplit((scheme, netloc, parsed.path.rstrip("/"), "", ""))

    def get_feedback_url(self) -> str:
        base_url = self._normalized_site_url()
        return f"{base_url}{reverse('feedback:facility_submit', kwargs={'facility_id': self.pk})}"

    def generate_qr_code(self, save: bool = True) -> None:
        import qrcode

        qr = qrcode.QRCode(box_size=10, border=2)
        qr.add_data(self.get_feedback_url())
        qr.make(fit=True)

        image = qr.make_image(fill_color="black", back_color="white")
        buffer = BytesIO()
        image.save(buffer, format="PNG")
        facility_slug = slugify(self.name) or f"facility-{self.pk}"
        filename = f"{facility_slug}-{self.pk}-qr.png"
        self.qr_code.save(filename, ContentFile(buffer.getvalue()), save=save)

    def save(self, *args, **kwargs):
        previous_name = None
        if self.pk:
            previous_name = type(self).objects.filter(pk=self.pk).values_list("name", flat=True).first()

        regenerate = self.pk is None or not self.qr_code or previous_name != self.name
        super().save(*args, **kwargs)
        if regenerate:
            # The facility ID is part of the QR payload, so we generate the image after the first save.
            self.generate_qr_code(save=False)
            super().save(update_fields=["qr_code"])
