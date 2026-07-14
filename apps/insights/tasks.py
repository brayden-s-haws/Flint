from __future__ import annotations

import logging

from celery import shared_task
from django.contrib.contenttypes.models import ContentType
from django.db import transaction

from apps.catalog.models import Table
from apps.insights.cross_source_pipeline import run_discovery_for_pair
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

@shared_task
def run_cross_source_discovery_task(account_id: int, source_a_id: int, source_b_id: int) -> None:
    try:
        source_a = Source.objects.get(pk=source_a_id, account_id=account_id)
        source_b = Source.objects.get(pk=source_b_id, account_id=account_id)
        created = run_discovery_for_pair(source_a, source_b)
        logger.info("Cross-source discovery for sources %s+%s (account %s) created %s insights", source_a, source_b, account_id, created)
    except Exception:
        logger.exception("Cross-source discovery failed for sources %s+%s (account %s)", source_a_id, source_b_id, account_id)

@shared_task
def generate_intra_source_use_cases_task(source_id: int, placeholder_id: int) -> None:
    source = Source.objects.get(pk=source_id)
    placeholder = Insight.objects.get(pk=placeholder_id)
    source_ct = ContentType.objects.get_for_model(Source)
    try:
        use_cases = get_service('anthropic').generate_intra_source_use_case(source)
        with transaction.atomic():
            for uc in use_cases:
                insight = Insight.objects.create(account=source.account, text=uc['title'], insight_type='use_case_suggestion', status='active', structured_data=uc)
                InsightTarget.objects.create(account=source.account, insight=insight, content_type=source_ct, object_id=source.pk)
            placeholder.delete()
    except Exception:
        logger.exception("Failed to generate intra-source use cases for source %s", source_id)
        placeholder.status = 'failed'
        placeholder.save()
