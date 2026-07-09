from django.contrib import messages
from django.contrib.auth.decorators import login_required, user_passes_test
from django.http import FileResponse, Http404
from django.shortcuts import get_object_or_404, redirect
from django.utils.text import slugify

from .models import Facility


def _staff_required(user):
    return user.is_authenticated and user.is_staff


@login_required
@user_passes_test(_staff_required)
def download_qr_code(request, pk):
    facility = get_object_or_404(Facility, pk=pk)
    if not facility.qr_code:
        raise Http404("QR code not found.")

    download_name = f"{slugify(facility.name) or 'facility'}-{facility.pk}-qr.png"

    return FileResponse(
        facility.qr_code.open("rb"),
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
