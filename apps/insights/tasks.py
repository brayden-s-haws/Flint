from __future__ import annotations

import logging

from celery import shared_task
from django.contrib.contenttypes.models import ContentType

from apps.catalog.models import Table
from apps.insights.models import Insight, InsightTarget
from apps.insights.services.provider import get_service
from apps.sources.models import Source

logger = logging.getLogger(__name__)


@shared_task
def generate_table_description_task(insight_id: int) -> None:
    insight = Insight.objects.get(pk=insight_id)
    table_ct = ContentType.objects.get_for_model(Table)
    target = InsightTarget.objects.get(insight=insight, content_type=table_ct)
    table = target.target
    try:
        service = get_service('anthropic')
        text = service.generate_table_description(table)
        insight.text = text
        insight.status = 'active'
        insight.save()
    except Exception:
        logger.exception("Failed to generate description for insight %s", insight_id)
        insight.status = 'failed'
        insight.save()

@shared_task
def generate_source_overview_task(insight_id: int) -> None:
    insight = Insight.objects.get(pk=insight_id)
    source_ct = ContentType.objects.get_for_model(Source)
    target = InsightTarget.objects.get(insight=insight, content_type=source_ct)
    source = target.target
    try:
        text = get_service('anthropic').generate_source_overview(source)
        insight.text = text
        insight.status = 'active'
        insight.save()
    except Exception:
        logger.exception("Failed to generate source overview for insight %s", insight_id)
        insight.status = 'failed'
        insight.save()