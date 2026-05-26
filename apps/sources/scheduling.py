from __future__ import annotations
import json

from django.conf import settings
from django_celery_beat.models import CrontabSchedule, PeriodicTask

from .models import Source, SourceSchedule

FREQUENCY_TO_CRONTAB: dict[str, dict[str, str]] = {
    'hourly': {'minute': '0', 'hour': '*', 'day_of_month': '*', 'month_of_year': '*', 'day_of_week': '*'},
    'daily': {'minute': '0', 'hour': '6', 'day_of_month': '*', 'month_of_year': '*', 'day_of_week': '*'},
    'weekly': {'minute': '0', 'hour': '6', 'day_of_month': '*', 'month_of_year': '*', 'day_of_week': '1'},
    'monthly': {'minute': '0', 'hour': '6', 'day_of_month': '1', 'month_of_year': '*', 'day_of_week': '*'},
}

def create_or_update_source_schedule(source: Source, frequency: str) -> tuple[SourceSchedule, bool]:
    fields = FREQUENCY_TO_CRONTAB.get(frequency)
    if fields is None:
        raise ValueError(f"Invalid frequency: {frequency}")
    crontab, _ = CrontabSchedule.objects.get_or_create(**fields, timezone=settings.TIME_ZONE)
    existing = SourceSchedule.objects.filter(source=source).first()
    if existing:
        existing.frequency = frequency
        existing.is_enabled = True
        if existing.periodic_task:
            existing.periodic_task.crontab = crontab
            existing.periodic_task.enabled = True
            existing.periodic_task.save()
        else:
            pt = PeriodicTask.objects.create(name=f'sync-source-{source.pk}', task='apps.sources.tasks.run_scheduled_sync', crontab=crontab, args=json.dumps([source.pk]), enabled=True)
            existing.periodic_task = pt
        existing.save()
        return existing, False
    else:
        pt = PeriodicTask.objects.create(name=f'sync-source-{source.pk}', task='apps.sources.tasks.run_scheduled_sync', crontab=crontab, args=json.dumps([source.pk]), enabled=True)
        schedule = SourceSchedule.objects.create(source=source, account=source.account, frequency=frequency, is_enabled=True, periodic_task=pt)
        return schedule, True

def disable_source_schedule(source: Source) -> None:
    try:
        schedule = source.schedule
    except SourceSchedule.DoesNotExist:
        return
    schedule.is_enabled = False
    if schedule.periodic_task:
        schedule.periodic_task.enabled = False
        schedule.periodic_task.save()
    schedule.save()

def delete_source_schedule(source: Source) -> None:
    try:
        schedule = source.schedule
    except SourceSchedule.DoesNotExist:
        return
    if schedule.periodic_task:
        schedule.periodic_task.delete()
    schedule.delete()

def toggle_source_schedule(source: Source) -> tuple[SourceSchedule, bool]:
    schedule = source.schedule
    was_paused = not schedule.is_enabled
    schedule.is_enabled = not schedule.is_enabled
    schedule.save()
    if schedule.periodic_task:
        schedule.periodic_task.enabled = schedule.is_enabled
        schedule.periodic_task.save()
    return schedule, was_paused
