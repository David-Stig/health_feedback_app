from urllib.parse import urlencode

from django.contrib import messages
from django.core.exceptions import PermissionDenied, ValidationError
from django.core.paginator import Paginator
from django.db.models import Avg, Count, Q
from django.http import HttpResponse
from django.shortcuts import get_object_or_404, redirect
from django.urls import reverse, reverse_lazy
from django.utils import timezone
from django.views.generic import CreateView, DeleteView, DetailView, FormView, ListView, TemplateView, View

from feedback.audit import log_bulk_event
from feedback.import_tools import (
    build_error_report_workbook,
    import_validated_batch,
    rollback_import_batch,
    validate_import_batch,
    workbook_template_response,
)
from feedback.models import CollectionSession, Feedback, ImportBatch
from feedback.submission_service import create_feedback_entries_from_cleaned_data

from .bulk_forms import AssistedCaptureForm, CollectionSessionForm, ImportUploadForm
from .mixins import PermissionOrStaffRequiredMixin, accessible_facilities_for_user


class FacilityScopedBulkMixin(PermissionOrStaffRequiredMixin):
    def get_accessible_facilities(self):
        return accessible_facilities_for_user(self.request.user)

    def ensure_facility_access(self, facility):
        if not self.request.user.is_staff and not self.get_accessible_facilities().filter(pk=facility.pk).exists():
            raise PermissionDenied


class SpreadsheetImportsDisabledView(FacilityScopedBulkMixin, View):
    permission_required = "feedback.view_collectionsession"

    def dispatch(self, request, *args, **kwargs):
        messages.info(request, "Spreadsheet imports are temporarily disabled.")
        return redirect("dashboard:bulk_session_list")


class CollectionSessionListView(FacilityScopedBulkMixin, ListView):
    permission_required = "feedback.view_collectionsession"
    template_name = "dashboard/bulk_session_list.html"
    context_object_name = "sessions"
    paginate_by = 10
    model = CollectionSession

    def get_queryset(self):
        queryset = CollectionSession.objects.select_related("facility", "collected_by").annotate(
            response_total=Count("feedback_entries", filter=Q(feedback_entries__is_active=True))
        )
        facility_queryset = self.get_accessible_facilities()
        if not self.request.user.is_staff:
            queryset = queryset.filter(facility__in=facility_queryset)

        self.search_query = (self.request.GET.get("search") or "").strip()
        if self.search_query:
            queryset = queryset.filter(
                Q(session_code__icontains=self.search_query)
                | Q(campaign_name__icontains=self.search_query)
                | Q(facility__name__icontains=self.search_query)
            )
        return queryset.order_by("-created_at")

    def get_context_data(self, **kwargs):
        context = super().get_context_data(**kwargs)
        context["search_query"] = getattr(self, "search_query", "")
        return context


class CollectionSessionCreateView(FacilityScopedBulkMixin, CreateView):
    permission_required = "feedback.add_collectionsession"
    form_class = CollectionSessionForm
    model = CollectionSession
    template_name = "dashboard/bulk_session_form.html"
    success_url = reverse_lazy("dashboard:bulk_session_list")

    def get_form_kwargs(self):
        kwargs = super().get_form_kwargs()
        kwargs["user"] = self.request.user
        return kwargs

    def form_valid(self, form):
        form.instance.collected_by = self.request.user
        response = super().form_valid(form)
        log_bulk_event("collection_session_created", actor=self.request.user, collection_session=self.object)
        messages.success(self.request, "Collection session created successfully.")
        return response


class CollectionSessionDetailView(FacilityScopedBulkMixin, DetailView):
    permission_required = "feedback.view_collectionsession"
    model = CollectionSession
    template_name = "dashboard/bulk_session_detail.html"
    context_object_name = "session"

    def get_queryset(self):
        queryset = CollectionSession.objects.select_related("facility", "collected_by")
        if self.request.user.is_staff:
            return queryset
        return queryset.filter(facility__in=self.get_accessible_facilities())

    def get_context_data(self, **kwargs):
        context = super().get_context_data(**kwargs)
        context["responses"] = (
            self.object.feedback_entries.filter(is_active=True)
            .select_related("facility", "captured_by")
            .prefetch_related("rating_responses")
            .annotate(
                rating_response_total=Count("rating_responses", distinct=True),
                average_rating_value=Avg("rating_responses__rating"),
            )
            .order_by("-created_at")[:20]
        )
        return context


class CollectionSessionDeleteView(FacilityScopedBulkMixin, DeleteView):
    permission_required = "feedback.delete_collectionsession"
    model = CollectionSession
    template_name = "dashboard/bulk_session_confirm_delete.html"
    success_url = reverse_lazy("dashboard:bulk_session_list")
    context_object_name = "session"

    def get_queryset(self):
        queryset = CollectionSession.objects.select_related("facility", "collected_by")
        if self.request.user.is_staff:
            return queryset
        return queryset.filter(facility__in=self.get_accessible_facilities())

    def form_valid(self, form):
        session_code = self.object.session_code
        log_bulk_event("collection_session_deleted", actor=self.request.user, collection_session=self.object)
        messages.success(self.request, f"Session {session_code} deleted successfully.")
        return super().form_valid(form)


class CollectionSessionStatusUpdateView(FacilityScopedBulkMixin, View):
    permission_required = "feedback.change_collectionsession"

    STATUS_TRANSITIONS = {
        "start": CollectionSession.Status.ACTIVE,
        "pause": CollectionSession.Status.PAUSED,
        "resume": CollectionSession.Status.ACTIVE,
        "complete": CollectionSession.Status.COMPLETED,
        "cancel": CollectionSession.Status.CANCELLED,
    }

    EVENT_MAP = {
        "start": "collection_session_started",
        "pause": "collection_session_paused",
        "resume": "collection_session_resumed",
        "complete": "collection_session_completed",
        "cancel": "collection_session_cancelled",
    }

    def post(self, request, pk, action):
        session = get_object_or_404(CollectionSession, pk=pk)
        self.ensure_facility_access(session.facility)

        if action not in self.STATUS_TRANSITIONS:
            raise PermissionDenied

        session.status = self.STATUS_TRANSITIONS[action]
        if session.status == CollectionSession.Status.COMPLETED and not session.end_date:
            session.end_date = timezone.localdate()
        session.save(update_fields=["status", "end_date", "updated_at"])
        log_bulk_event(self.EVENT_MAP[action], actor=request.user, collection_session=session)
        messages.success(request, f"Session {session.session_code} updated to {session.get_status_display().lower()}.")
        return redirect("dashboard:bulk_session_detail", pk=session.pk)


class AssistedCaptureView(FacilityScopedBulkMixin, FormView):
    permission_required = "feedback.capture_assisted_feedback"
    template_name = "dashboard/bulk_assisted_capture.html"
    form_class = AssistedCaptureForm

    def dispatch(self, request, *args, **kwargs):
        self.session = get_object_or_404(
            CollectionSession.objects.select_related("facility", "collected_by"),
            pk=kwargs["pk"],
        )
        self.ensure_facility_access(self.session.facility)
        if not self.session.accepts_responses():
            messages.error(request, "This session is not currently accepting responses.")
            return redirect("dashboard:bulk_session_detail", pk=self.session.pk)
        return super().dispatch(request, *args, **kwargs)

    def get_form_kwargs(self):
        kwargs = super().get_form_kwargs()
        kwargs["facility_id"] = self.session.facility_id
        return kwargs

    def form_valid(self, form):
        ratings = {}
        comments = {}
        for category_value, _label in Feedback.Category.choices:
            rating_value = self.request.POST.get(f"rating_{category_value}")
            comment_value = self.request.POST.get(f"comment_{category_value}")
            if rating_value:
                ratings[category_value] = rating_value
                comments[category_value] = comment_value or ""

        if not ratings:
            form.add_error(None, "Please rate at least one category.")
            return self.form_invalid(form)

        create_feedback_entries_from_cleaned_data(
            facility=self.session.facility,
            cleaned_data=form.cleaned_data,
            ratings=ratings,
            comments=comments,
            submission_source=Feedback.SubmissionSource.ASSISTED_CAPTURE,
            collection_session=self.session,
            captured_by=self.request.user,
            submitted_on=timezone.localdate(),
        )
        log_bulk_event(
            "assisted_response_captured",
            actor=self.request.user,
            collection_session=self.session,
            details={"rating_categories": list(ratings.keys())},
        )

        action = self.request.POST.get("capture_action", "next")
        if action == "end":
            self.session.status = CollectionSession.Status.COMPLETED
            self.session.end_date = timezone.localdate()
            self.session.save(update_fields=["status", "end_date", "updated_at"])
            log_bulk_event("collection_session_completed", actor=self.request.user, collection_session=self.session)
            messages.success(self.request, "Final response saved and session completed.")
            return redirect("dashboard:bulk_session_detail", pk=self.session.pk)

        messages.success(self.request, "Response captured. Ready for the next respondent.")
        return redirect("dashboard:bulk_session_capture", pk=self.session.pk)

    def get_context_data(self, **kwargs):
        context = super().get_context_data(**kwargs)
        context["session"] = self.session
        context["response_count"] = self.session.feedback_entries.filter(is_active=True).count()
        context["categories"] = Feedback.Category.choices
        return context


class ImportBatchListView(FacilityScopedBulkMixin, ListView):
    permission_required = "feedback.view_importbatch"
    template_name = "dashboard/bulk_import_list.html"
    context_object_name = "batches"
    paginate_by = 10
    model = ImportBatch

    def get_queryset(self):
        queryset = ImportBatch.objects.select_related("facility", "collection_session", "uploaded_by")
        if not self.request.user.is_staff:
            queryset = queryset.filter(
                Q(facility__in=self.get_accessible_facilities())
                | Q(collection_session__facility__in=self.get_accessible_facilities())
            )
        return queryset.order_by("-uploaded_at")


class ImportTemplateDownloadView(FacilityScopedBulkMixin, View):
    permission_required = "feedback.add_importbatch"

    def get(self, request):
        workbook = workbook_template_response()
        response = HttpResponse(
            content_type="application/vnd.openxmlformats-officedocument.spreadsheetml.sheet"
        )
        response["Content-Disposition"] = 'attachment; filename="bulk-feedback-template.xlsx"'
        workbook.save(response)
        return response


class ImportBatchUploadView(FacilityScopedBulkMixin, FormView):
    permission_required = "feedback.add_importbatch"
    template_name = "dashboard/bulk_import_upload.html"
    form_class = ImportUploadForm

    def get_form_kwargs(self):
        kwargs = super().get_form_kwargs()
        kwargs["user"] = self.request.user
        return kwargs

    def form_valid(self, form):
        batch = form.save(commit=False)
        batch.original_filename = form.cleaned_data["stored_file"].name
        batch.uploaded_by = self.request.user
        batch.status = ImportBatch.Status.UPLOADED
        batch.save()
        log_bulk_event("spreadsheet_uploaded", actor=self.request.user, import_batch=batch)

        try:
            validate_import_batch(batch, self.get_accessible_facilities())
        except ValidationError as exc:
            batch.status = ImportBatch.Status.VALIDATION_FAILED
            batch.validation_summary = {"errors": exc.messages, "rows": []}
            batch.save(update_fields=["status", "validation_summary"])
            messages.error(self.request, "; ".join(exc.messages))
            return redirect("dashboard:bulk_import_detail", pk=batch.pk)

        messages.success(self.request, f"File uploaded and validated as batch {batch.batch_code}.")
        return redirect("dashboard:bulk_import_detail", pk=batch.pk)


class ImportBatchDetailView(FacilityScopedBulkMixin, TemplateView):
    permission_required = "feedback.view_importbatch"
    template_name = "dashboard/bulk_import_detail.html"

    def dispatch(self, request, *args, **kwargs):
        self.batch = get_object_or_404(
            ImportBatch.objects.select_related("facility", "collection_session", "uploaded_by"),
            pk=kwargs["pk"],
        )
        if not request.user.is_staff:
            accessible = self.get_accessible_facilities()
            facility_ok = self.batch.facility_id and accessible.filter(pk=self.batch.facility_id).exists()
            session_ok = (
                self.batch.collection_session_id
                and accessible.filter(pk=self.batch.collection_session.facility_id).exists()
            )
            if not (facility_ok or session_ok):
                raise PermissionDenied
        return super().dispatch(request, *args, **kwargs)

    def get_context_data(self, **kwargs):
        context = super().get_context_data(**kwargs)
        row_results = self.batch.validation_summary.get("rows", [])
        paginator = Paginator(row_results, 10)
        page_obj = paginator.get_page(self.request.GET.get("page"))
        context.update(
            {
                "batch": self.batch,
                "page_obj": page_obj,
                "row_results": page_obj.object_list,
            }
        )
        return context


class ImportBatchConfirmView(FacilityScopedBulkMixin, View):
    permission_required = "feedback.confirm_importbatch"

    def post(self, request, pk):
        batch = get_object_or_404(ImportBatch, pk=pk)
        try:
            import_validated_batch(batch, request.user)
        except ValidationError as exc:
            messages.error(request, "; ".join(exc.messages))
        else:
            messages.success(request, f"Import batch {batch.batch_code} processed successfully.")
        return redirect("dashboard:bulk_import_detail", pk=batch.pk)


class ImportBatchErrorReportView(FacilityScopedBulkMixin, View):
    permission_required = "feedback.download_import_errors"

    def get(self, request, pk):
        batch = get_object_or_404(ImportBatch, pk=pk)
        workbook = build_error_report_workbook(batch)
        log_bulk_event("import_error_report_downloaded", actor=request.user, import_batch=batch)
        response = HttpResponse(
            content_type="application/vnd.openxmlformats-officedocument.spreadsheetml.sheet"
        )
        response["Content-Disposition"] = f'attachment; filename="{batch.batch_code.lower()}-errors.xlsx"'
        workbook.save(response)
        return response


class ImportBatchRollbackView(FacilityScopedBulkMixin, TemplateView):
    permission_required = "feedback.rollback_importbatch"
    template_name = "dashboard/bulk_import_rollback_confirm.html"

    def dispatch(self, request, *args, **kwargs):
        self.batch = get_object_or_404(ImportBatch, pk=kwargs["pk"])
        return super().dispatch(request, *args, **kwargs)

    def post(self, request, *args, **kwargs):
        try:
            rollback_import_batch(self.batch, request.user)
        except ValidationError as exc:
            messages.error(request, "; ".join(exc.messages))
        else:
            messages.success(request, f"Import batch {self.batch.batch_code} rolled back successfully.")
        return redirect("dashboard:bulk_import_detail", pk=self.batch.pk)

    def get_context_data(self, **kwargs):
        context = super().get_context_data(**kwargs)
        context["batch"] = self.batch
        context["affected_count"] = self.batch.feedback_entries.filter(is_active=True).count()
        return context
