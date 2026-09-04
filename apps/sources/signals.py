""" Cleanup signals for source deletion: tears down scheduling and insight records that Django's cascade would otherwise leave behind. """
from __future__ import annotations

from typing import Any

from django.contrib.contenttypes.models import ContentType
from django.db.models import Q
from django.db.models.signals import post_delete, pre_delete
from django.dispatch import receiver
from django_celery_beat.models import PeriodicTask

from .models import SourceSchedule, Source
from apps.catalog.models import Table
from apps.insights.models import Insight, InsightTarget


@receiver(post_delete, sender=SourceSchedule)
def delete_periodic_task_on_source_delete(sender: type[SourceSchedule], instance: SourceSchedule, **kwargs: Any) -> None:
    """Delete the beat PeriodicTask a schedule pointed at once the SourceSchedule is gone, the FK is SET_NULL, so the task would otherwise be orphaned and keep firing."""
    if instance.periodic_task_id:
        PeriodicTask.objects.filter(pk=instance.periodic_task_id).delete()

@receiver(pre_delete, sender=Source)
def cleanup_insights_on_source_delete(sender: type[Source], instance: Source, **kwargs: Any) -> None:
    """
    - Hard-delete the insights targeting a source (its overview/use-cases) and all of its tables (their descriptions) before the source is removed.
    - Needed because InsightTarget links via a GenericForeignKey, which has no DB cascade. Without this the insights would be left dangling. Scoped to the source's account.
    """
    source_ct = ContentType.objects.get_for_model(Source)
    table_ct = ContentType.objects.get_for_model(Table)
    insight_ids = InsightTarget.objects.filter(Q(content_type=source_ct, object_id=instance.pk) | Q(content_type=table_ct, object_id__in=Table.objects.filter(schema__source=instance)),
                                               account=instance.account).values_list('insight_id', flat=True)
    Insight.objects.filter(pk__in=insight_ids).delete()