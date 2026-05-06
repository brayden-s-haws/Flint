from __future__ import annotations

# TODO(stub): Imports.
# - `import logging` — for the module-level logger so worker exceptions get traces in the worker console
# - `from celery import shared_task` — the decorator we use (NOT `from Flint.celery import app`); shared_task is
#   the recommended pattern for tasks defined inside Django apps because it doesn't bind to a specific app instance
# - `from django.contrib.contenttypes.models import ContentType` — used by the source-overview insight block
# - `from django.utils import timezone` — for setting `completed_at` on the sync log
# - From this app:
#     `from .connectors.registry import get_connector`
#     `from .encryption import decrypt_credentials`
#     `from .models import Source, SourceSyncLog`
# - From sibling apps:
#     `from apps.catalog.models import Schema, Table, Column, TableStatistics`
#     `from apps.insights.models import Insight, InsightTarget`
#     `from apps.insights.services.provider import get_service`

# TODO(stub): Module-level logger.
# - `logger = logging.getLogger(__name__)`
# - The worker logs to its own console; without `logger.exception(...)` calls, failed tasks fail silently.

# TODO(stub): Define `sync_source_task(source_id: int, sync_log_id: int) -> None`.
# - Decorate with `@shared_task` (no arguments needed; default config is fine).
# - Type hints required on both parameters and the return type per CLAUDE.md.
# - WHY IDs not objects: Celery serializes args as JSON. Django ORM objects are not JSON-serializable
#   and would also be stale by the time the worker picks the task up. Always pass IDs and re-query inside.
# - The view (which we'll modify in step 3b) creates the SourceSyncLog row with status='running' BEFORE calling
#   `sync_source_task.delay(...)`. So at task entry, the log row already exists — fetch it, don't create it.

#   ─── Inside the function body, follow this structure: ───

# TODO(stub): Re-query both the Source and SourceSyncLog from the database using the IDs passed in.
# - `source = Source.objects.get(pk=source_id)` and `sync_log = SourceSyncLog.objects.get(pk=sync_log_id)`.
# - If either is gone (deleted between enqueue and execution), the .get() will raise DoesNotExist — that's fine,
#   Celery will mark the task as failed and we don't need to handle it specially. The polling endpoint will see
#   no fresh `running` record and fall back to "no sync in progress."

# TODO(stub): Wrap the rest of the body in a try/except.
# - The try block covers the actual sync work (catalog discovery + DB writes + LLM source overview).
# - The except block writes failure state to `sync_log` and logs the exception. This is what the polling endpoint
#   reads to surface the error to the user — without it, a failed task is invisible from the UI.

# ─── Inside the try block ───

# TODO(stub): Decrypt credentials and instantiate the connector.
# - Mirror the existing view code at apps/sources/views.py:162-164:
#     `credentials = decrypt_credentials(source.credentials)`
#     `connector_class = get_connector(source.source_type.name)`
#     `connector = connector_class(credentials)`
# - The connector knows how to talk to the actual data source (PostgreSQL, demo, etc.).

# TODO(stub): Run catalog discovery and walk schemas → tables → columns.
# - `catalog = connector.discover_catalog()` returns a list of dicts, each with `name` and `tables`.
# - Maintain a `records_synced = 0` counter that increments once per table.
# - For each schema dict:
#     - `Schema.objects.get_or_create(source=source, name=schema_data['name'], defaults={'account': source.account})`
#     - For each table dict in `schema_data['tables']`:
#         - `Table.objects.get_or_create(schema=schema, name=table_data['name'], defaults={...})`
#         - `metadata = connector.get_table_metadata(schema_data['name'], table_data['name'])`
#         - Update `table.row_count`, `table.table_type`, then `.save()`
#         - `TableStatistics.objects.create(account=source.account, table=table, row_count=metadata['row_count'],
#           column_stats=metadata.get('column_stats', {}))`
#         - For each column dict in `table_data['columns']`:
#             - `Column.objects.get_or_create(table=table, name=col_data['name'], defaults={...})`
#             - Update data_type/nullable/primary_key, then save
#         - Increment `records_synced`
# - Copy the exact structure from apps/sources/views.py:166-194. The point of this step is moving code,
#   not refactoring. We can clean up nested loops in the bug-bash pass later.

# TODO(stub): Mark the sync_log as successful and save sync metadata.
# - `sync_log.completed_at = timezone.now()`
# - `sync_log.status = 'success'`
# - `sync_log.records_synced = records_synced`
# - `sync_log.save()`
# - If `source.first_synced_at is None`: set it to now() and `source.save()`. Mirrors current view behavior.

# TODO(stub): Generate the source overview insight if one doesn't exist yet.
# - This block mirrors apps/sources/views.py:202-211 verbatim. Don't refactor; just paste in.
# - `content_type = ContentType.objects.get_for_model(Source)`
# - Check `InsightTarget.objects.filter(...)` to see if an overview already exists for this source.
# - If not: nested try/except — call `get_service('anthropic').generate_source_overview(source)`, then create
#   the Insight + InsightTarget records. On exception: `logger.exception(...)` and continue (overview failure
#   should NOT fail the whole sync).
# - The nested try/except is intentional: a failing LLM call shouldn't roll back successful catalog sync.

# ─── Inside the except block (catches anything in the try block) ───

# TODO(stub): Record the failure on sync_log.
# - `sync_log.status = 'failed'`
# - `sync_log.error_message = str(exc)` (use a meaningful name like `exc` for the caught exception)
# - `sync_log.completed_at = timezone.now()`
# - `sync_log.save()`

# TODO(stub): Log the exception with traceback for worker-console debugging.
# - `logger.exception("Source sync failed for source %s", source_id)`
# - logger.exception (NOT logger.error) automatically captures the traceback. Critical for debugging failures
#   that the polling endpoint will only show as a one-line error_message.

# TODO(stub): The function returns None (the @shared_task decorator handles task completion bookkeeping
# regardless of return value). Don't return the sync_log — the polling endpoint reads it directly from the DB.