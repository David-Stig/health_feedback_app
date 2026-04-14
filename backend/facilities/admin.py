from django.contrib import admin

from .models import Facility


@admin.register(Facility)
class FacilityAdmin(admin.ModelAdmin):
    list_display = ("name", "district", "province", "created_at")
    list_filter = ("province", "district")
    search_fields = ("name", "district", "province")
