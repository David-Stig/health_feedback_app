from django.db import models
from django.core.files.base import ContentFile
from django.urls import reverse
from django.conf import settings
from io import BytesIO


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

    def get_feedback_url(self) -> str:
        base_url = settings.SITE_URL.rstrip("/")
        return f"{base_url}{reverse('feedback:submit')}?facility_id={self.pk}"

    def generate_qr_code(self, save: bool = True) -> None:
        import qrcode

        qr = qrcode.QRCode(box_size=10, border=2)
        qr.add_data(self.get_feedback_url())
        qr.make(fit=True)

        image = qr.make_image(fill_color="black", back_color="white")
        buffer = BytesIO()
        image.save(buffer, format="PNG")
        filename = f"facility-{self.pk}-qr.png"
        self.qr_code.save(filename, ContentFile(buffer.getvalue()), save=save)

    def save(self, *args, **kwargs):
        regenerate = self.pk is None or not self.qr_code
        super().save(*args, **kwargs)
        if regenerate:
            # The facility ID is part of the QR payload, so we generate the image after the first save.
            self.generate_qr_code(save=False)
            super().save(update_fields=["qr_code"])
