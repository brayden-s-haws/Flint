""" Celery tasks that run source syncs off the request cycle: the main sync pipeline and the scheduled-sync entry point invoked by celery-beat. """
from __future__ import annotations

import logging

from celery import shared_task
from django.contrib.contenttypes.models import ContentType
from django.utils import timezone

from .connectors.registry import build_connector
from .encryption import decrypt_credentials
from .models import Source, SourceSyncLog, SourceSchedule
from apps.catalog.models import Schema, Table, Column, TableStatistics
from apps.insights.models import Insight, InsightTarget
from apps.insights.tasks import generate_source_overview_task


logger = logging.getLogger(__name__)


@shared_task
def sync_source_task(source_id: int, sync_log_id: int) -> None:
    """
    - The core sync pipeline: decrypt credentials, build the connector, discover the catalog, and upsert Schema/Table/Column plus a TableStatistics snapshot for the account.
    - On success marks the sync log, sets first_synced_at on the first-ever sync, then ensures a source-overview insight exists and dispatches its async generation (regenerating only if the prior one failed).
    - Any failure is caught: the sync log is marked failed with the error message, and the exception is logged. Runs under the macOS threads pool (see settings.py) to avoid fork-safety crashes for 
    local development.
    """
    source = Source.objects.get(pk=source_id)
    sync_log = SourceSyncLog.objects.get(pk=sync_log_id)
    logger.info("Starting sync for source %s of type %s with sync log %s", source.id, source.source_type, sync_log_id)
    try:
        credentials = decrypt_credentials(source.credentials)
        connector = build_connector(source.source_type, credentials)
        catalog = connector.discover_catalog()
        records_synced = 0
        for schema_data in catalog:
            schema, _ = Schema.objects.get_or_create(
                source=source, name=schema_data['name'],
                defaults={'account': source.account}
            )
            for table_data in schema_data['tables']:
                table, _ = Table.objects.get_or_create(
                    schema=schema, name=table_data['name'],
                    defaults={'account': source.account, 'table_type': table_data['table_type']}
                )
                metadata = connector.get_table_metadata(schema_data['name'], table_data['name'])
                table.row_count = metadata['row_count']
                table.table_type = table_data['table_type']
                table.save()
                TableStatistics.objects.create(
                    account=source.account, table=table,
                    row_count=metadata['row_count'], column_stats=metadata.get('column_stats', {})
                )
                for col_data in table_data['columns']:
                    col, _ = Column.objects.get_or_create(
                        table=table, name=col_data['name'],
                        defaults={'account': source.account, 'data_type': col_data['data_type'], 'nullable': col_data['nullable'], 'primary_key': col_data['primary_key']}
                    )
                    col.data_type = col_data['data_type']
                    col.nullable = col_data['nullable']
                    col.primary_key = col_data['primary_key']
                    col.save()
                records_synced += 1
        sync_log.completed_at = timezone.now()
        sync_log.status = 'success'
        sync_log.records_synced = records_synced
        if source.first_synced_at is None:
            source.first_synced_at = timezone.now()
            source.save()
        sync_log.save()
        duration = (sync_log.completed_at - sync_log.started_at).total_seconds()
        logger.info("Sync completed for source %s of type %s with sync log %s: %s tables synced in %s seconds", source.id, source.source_type, sync_log_id, records_synced, duration)
        content_type = ContentType.objects.get_for_model(Source)
        existing = InsightTarget.objects.filter(content_type=content_type, object_id=source.pk, account=source.account, insight__insight_type='source_overview').select_related('insight').first()
        if existing and existing.insight.status == 'failed':
            existing.insight.delete()
            existing = None
        if existing is None:
            insight = Insight.objects.create(account=source.account, text='', insight_type='source_overview', status='pending', insight_prompt=None)
            InsightTarget.objects.create(account=source.account, insight=insight, content_type=content_type, object_id=source.pk)
            generate_source_overview_task.delay(insight.pk)
    except Exception as e:
        sync_log.status = 'failed'
        sync_log.error_message = str(e)
        sync_log.completed_at = timezone.now()
        sync_log.save()
        logger.exception("Source sync failed for source %s with sync log %s", source_id, sync_log_id)

@shared_task
def run_scheduled_sync(source_id: int) -> None:
    """
    - celery-beat entry point for automated syncs: the task a source's PeriodicTask fires on its cron schedule.
    - Bails out (logging a warning, no error) if the source is gone, has no schedule, or the schedule is disabled; otherwise opens a running sync log and hands off to sync_source_task.
    """
    try:
        source = Source.objects.get(pk=source_id)
    except Source.DoesNotExist:
        logger.warning("Source %s does not exist", source_id)
        return
    try:
        schedule = source.schedule
    except SourceSchedule.DoesNotExist:
        logger.warning("Schedule sync fired but source %s has no schedule", source_id)
        return
    if not schedule.is_enabled:
        logger.warning("Source schedule is disabled for source %s ", source_id)
        return
    sync_log = SourceSyncLog.objects.create(source=source, account=source.account, status='running', started_at=timezone.now())
    sync_source_task.delay(source.pk, sync_log.pk)

