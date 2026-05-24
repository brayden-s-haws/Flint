from __future__ import annotations

from typing import Any

from django.db.models.signals import post_delete
from django.dispatch import receiver
from django_celery_beat.models import PeriodicTask

from .models import SourceSchedule


@receiver(post_delete, sender=SourceSchedule)
def delete_periodic_task_on_source_delete(sender: type[SourceSchedule], instance: SourceSchedule, **kwargs: Any) -> None:
    if instance.periodic_task_id:
        PeriodicTask.objects.filter(pk=instance.periodic_task_id).delete()