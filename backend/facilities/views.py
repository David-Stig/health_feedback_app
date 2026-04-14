from django.contrib.auth.decorators import login_required, user_passes_test
from django.http import FileResponse, Http404
from django.shortcuts import get_object_or_404

from .models import Facility


def _staff_required(user):
    return user.is_authenticated and user.is_staff


@login_required
@user_passes_test(_staff_required)
def download_qr_code(request, pk):
    facility = get_object_or_404(Facility, pk=pk)
    if not facility.qr_code:
        raise Http404("QR code not found.")

    return FileResponse(
        facility.qr_code.open("rb"),
        as_attachment=True,
        filename=facility.qr_code.name.split("/")[-1],
    )
