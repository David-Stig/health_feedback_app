from django.contrib import admin

from .models import Feedback, RatingResponse


class RatingResponseInline(admin.TabularInline):
    model = RatingResponse
    extra = 0
    fields = ("category", "rating", "comment")
    readonly_fields = ()


@admin.register(Feedback)
class FeedbackAdmin(admin.ModelAdmin):
    list_display = ("created_at", "facility", "submission_source", "rating_response_total")
    list_filter = ("submission_source", "facility__province", "facility__district")
    search_fields = ("comment", "facility__name")
    autocomplete_fields = ("facility",)
    inlines = [RatingResponseInline]

    def get_queryset(self, request):
        queryset = super().get_queryset(request)
        return queryset.prefetch_related("rating_responses")

    @admin.display(description="Ratings answered")
    def rating_response_total(self, obj):
        return obj.rating_responses.count()
