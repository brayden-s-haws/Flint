""" All insight generations are handled through async tasks. This is done because they are handled by third-party APIs and can take varying amounts of time. Using tasks ensures the user is not
blocked while they wait for the insight to be generated. For system-managed insights, Anthropic is the default model provider. """
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
    """
    - When a user views a table for the first time, we generate a description of the table.
    - On later views, we use the stored description, and the task is not executed.
    """
    insight = Insight.objects.get(pk=insight_id)
    table_ct = ContentType.objects.get_for_model(Table)
    target = InsightTarget.objects.get(insight=insight, content_type=table_ct)
    table = target.target
    try:
        service = get_service('anthropic')
        logger.info("Starting table description generation for insight %s with target %s", insight_id, table)
        text = service.generate_table_description(table)
        insight.text = text
        insight.status = 'active'
        insight.save()
        logger.info("Finished table description generation for insight %s", insight_id)
    except Exception:
        logger.exception("Failed to generate table description for insight %s", insight_id)
        insight.status = 'failed'
        insight.save()

@shared_task
def generate_source_overview_task(insight_id: int) -> None:
    """
    Runs during source sync. Generates an overview only when the source has no overview yet (or the prior attempt failed); an existing active overview is reused on later syncs.
    """
    insight = Insight.objects.get(pk=insight_id)
    source_ct = ContentType.objects.get_for_model(Source)
    target = InsightTarget.objects.get(insight=insight, content_type=source_ct)
    source = target.target
    try:
        logger.info("Starting source overview generation for insight %s with target %s", insight_id, source)
        text = get_service('anthropic').generate_source_overview(source)
        insight.text = text
        insight.status = 'active'
        insight.save()
        logger.info("Finished source overview generation for insight %s", insight_id)
    except Exception:
        logger.exception("Failed to generate source overview for insight %s", insight_id)
        insight.status = 'failed'
        insight.save()

@shared_task
def run_cross_source_discovery_task(account_id: int, source_a_id: int, source_b_id: int) -> None:
    """
    - When the user invokes the cross-source discovery feature, we generate potential use cases for combining the two sources.
    - This is currently the longest-running task and can take several minutes to complete. The UI has handling to assure the user that generation is running.
    - This task can be invoked multiple times for the same pair of sources. The outputs of each run are stored and displayed to the user.
    """
    try:
        source_a = Source.objects.get(pk=source_a_id, account_id=account_id)
        source_b = Source.objects.get(pk=source_b_id, account_id=account_id)
        logger.info("Starting cross-source discovery for sources %s+%s (account %s)", source_a_id, source_b_id, account_id)
        created = run_discovery_for_pair(source_a, source_b)
        logger.info("Finished cross-source discovery for sources %s+%s (account %s) created %s insights", source_a_id, source_b_id, account_id, created)
    except Exception:
        logger.exception("Cross-source discovery failed for sources %s+%s (account %s)", source_a_id, source_b_id, account_id)

@shared_task
def generate_intra_source_use_cases_task(source_id: int, placeholder_id: int) -> None:
    """
    - When the user invokes the intra-source discovery feature, we generate potential use cases for using the data from that source.
    - When invoked, a placeholder insight is created upstream and passed to the task with a status of 'pending'. Status is tracked and updated when the task fails or deleted in successful runs.
    - This task can be invoked multiple times for a source. The outputs of each run are stored and displayed to the user.
    """
    source = Source.objects.get(pk=source_id)
    placeholder = Insight.objects.get(pk=placeholder_id)
    source_ct = ContentType.objects.get_for_model(Source)
    try:
        logger.info("Starting intra-source use cases generation for source %s using placeholder %s", source_id, placeholder_id)
        use_cases = get_service('anthropic').generate_intra_source_use_case(source)
        with transaction.atomic():
            for uc in use_cases:
                insight = Insight.objects.create(account=source.account, text=uc['title'], insight_type='use_case_suggestion', status='active', structured_data=uc)
                InsightTarget.objects.create(account=source.account, insight=insight, content_type=source_ct, object_id=source.pk)
            placeholder.delete()
            logger.info("Finished intra-source use case generation for source %s", source_id)
    except Exception:
        logger.exception("Failed to generate intra-source use cases for source %s (placeholder %s)", source_id, placeholder_id)
        placeholder.status = 'failed'
        placeholder.save()
