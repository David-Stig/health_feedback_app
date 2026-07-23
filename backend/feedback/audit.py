from feedback.models import BulkActionAuditLog, CollectionSession, ImportBatch


def log_bulk_event(
    event_type: str,
    *,
    actor=None,
    collection_session: CollectionSession | None = None,
    import_batch: ImportBatch | None = None,
    details: dict | None = None,
) -> BulkActionAuditLog:
    return BulkActionAuditLog.objects.create(
        event_type=event_type,
        actor=actor,
        collection_session=collection_session,
        import_batch=import_batch,
        details=details or {},
    )
