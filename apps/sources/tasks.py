from __future__ import annotations

import logging

from celery import shared_task
from django.contrib.contenttypes.models import ContentType
from django.utils import timezone

from .connectors.registry import get_connector
from .encryption import decrypt_credentials
from .models import Source, SourceSyncLog
from apps.catalog.models import Schema, Table, Column, TableStatistics
from apps.insights.models import Insight, InsightTarget
from apps.insights.services.provider import get_service

logger = logging.getLogger(__name__)


@shared_task
def sync_source_task(source_id: int, sync_log_id: int) -> None:
    source = Source.objects.get(pk=source_id)
    sync_log = SourceSyncLog.objects.get(pk=sync_log_id)
    try:
        credentials = decrypt_credentials(source.credentials)
        connector_class = get_connector(source.source_type.name)
        connector = connector_class(credentials)
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
        content_type = ContentType.objects.get_for_model(Source)
        already_exists = InsightTarget.objects.filter(content_type=content_type, object_id=source.pk, account=source.account).exists()
        if not already_exists:
            try:
                service = get_service('anthropic')
                text = service.generate_source_overview(source)
                insight = Insight.objects.create(account=source.account, text=text, insight_type='source_overview', status='active', insight_prompt=None)
                InsightTarget.objects.create(account=source.account, insight=insight, content_type=content_type, object_id=source.pk)
            except Exception:
                logger.exception("Failed to generate source overview for source %s", source.pk)
    except Exception as e:
        sync_log.status = 'failed'
        sync_log.error_message = str(e)
        sync_log.completed_at = timezone.now()
        sync_log.save()
        logger.exception("Source sync failed for source %s", source_id)