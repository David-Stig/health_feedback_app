from django.contrib import admin

from .models import Feedback


@admin.register(Feedback)
class FeedbackAdmin(admin.ModelAdmin):
    list_display = ("created_at", "facility", "rating", "category")
    list_filter = ("category", "rating", "facility__province", "facility__district")
    search_fields = ("comment", "facility__name")
    autocomplete_fields = ("facility",)
