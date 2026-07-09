from django.contrib import messages
from django.contrib.auth.decorators import login_required, user_passes_test
from django.http import FileResponse, Http404
from django.shortcuts import get_object_or_404, redirect
from django.utils.text import slugify
from io import BytesIO

from PIL import Image, ImageDraw, ImageFont

from .models import Facility


def _staff_required(user):
    return user.is_authenticated and user.is_staff


def _build_labeled_qr_download(facility):
    facility.qr_code.open("rb")
    qr_image = Image.open(facility.qr_code)
    qr_image.load()
    qr_image = qr_image.convert("RGB")

    padding = 24
    spacing = 16
    font = ImageFont.load_default()
    label_text = facility.name

    scratch_image = Image.new("RGB", (1, 1), "white")
    draw = ImageDraw.Draw(scratch_image)
    text_bbox = draw.textbbox((0, 0), label_text, font=font)
    text_width = text_bbox[2] - text_bbox[0]
    text_height = text_bbox[3] - text_bbox[1]

    canvas_width = max(qr_image.width + (padding * 2), text_width + (padding * 2))
    canvas_height = padding + text_height + spacing + qr_image.height + padding
    canvas = Image.new("RGB", (canvas_width, canvas_height), "white")
    canvas_draw = ImageDraw.Draw(canvas)

    text_x = (canvas_width - text_width) // 2
    text_y = padding
    canvas_draw.text((text_x, text_y), label_text, fill="black", font=font)

    qr_x = (canvas_width - qr_image.width) // 2
    qr_y = text_y + text_height + spacing
    canvas.paste(qr_image, (qr_x, qr_y))

    output = BytesIO()
    canvas.save(output, format="PNG")
    output.seek(0)
    return output


@login_required
@user_passes_test(_staff_required)
def download_qr_code(request, pk):
    facility = get_object_or_404(Facility, pk=pk)
    if not facility.qr_code:
        raise Http404("QR code not found.")

    download_name = f"{slugify(facility.name) or 'facility'}-{facility.pk}-qr.png"
    labeled_qr = _build_labeled_qr_download(facility)

    return FileResponse(
        labeled_qr,
        as_attachment=True,
        filename=download_name,
    )


@login_required
@user_passes_test(_staff_required)
def regenerate_qr_code(request, pk):
    if request.method != "POST":
        raise Http404()

    facility = get_object_or_404(Facility, pk=pk)
    facility.generate_qr_code(save=False)
    facility.save(update_fields=["qr_code"])
    messages.success(request, f"QR code regenerated for {facility.name}.")
    return redirect("dashboard:facility_detail", pk=facility.pk)


@login_required
@user_passes_test(_staff_required)
def bulk_regenerate_qr_codes(request):
    if request.method != "POST":
        raise Http404()

    regenerated_count = 0
    for facility in Facility.objects.all():
        facility.generate_qr_code(save=False)
        facility.save(update_fields=["qr_code"])
        regenerated_count += 1

    messages.success(request, f"Regenerated QR codes for {regenerated_count} facilities.")
    return redirect("dashboard:facility_list")
