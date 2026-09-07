""" Helpers that keep a source's SourceSchedule in sync with its underlying django_celery_beat PeriodicTask/CrontabSchedule. All schedule mutations go through here so the two stay consistent. """
from __future__ import annotations
import json
import logging

from django.conf import settings
from django_celery_beat.models import CrontabSchedule, PeriodicTask

from .models import Source, SourceSchedule


logger = logging.getLogger(__name__)


# Translates the user-facing frequency choices into concrete crontab fields (daily/weekly/monthly run at 06:00 in the project timezone).
FREQUENCY_TO_CRONTAB: dict[str, dict[str, str]] = {
    'hourly': {'minute': '0', 'hour': '*', 'day_of_month': '*', 'month_of_year': '*', 'day_of_week': '*'},
    'daily': {'minute': '0', 'hour': '6', 'day_of_month': '*', 'month_of_year': '*', 'day_of_week': '*'},
    'weekly': {'minute': '0', 'hour': '6', 'day_of_month': '*', 'month_of_year': '*', 'day_of_week': '1'},
    'monthly': {'minute': '0', 'hour': '6', 'day_of_month': '1', 'month_of_year': '*', 'day_of_week': '*'},
}

def create_or_update_source_schedule(source: Source, frequency: str) -> tuple[SourceSchedule, bool]:
    """
    - Create or update a source's schedule at the given frequency, creating/repointing the backing PeriodicTask (which runs run_scheduled_sync for this source) and re-enabling it.
    - Returns (schedule, created) where created is True only when a new schedule was made. Raises ValueError for an unknown frequency.
    """
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
        logger.info("Updated schedule for source %s, runs %s", source.pk, frequency)
        return existing, False
    else:
        pt = PeriodicTask.objects.create(name=f'sync-source-{source.pk}', task='apps.sources.tasks.run_scheduled_sync', crontab=crontab, args=json.dumps([source.pk]), enabled=True)
        schedule = SourceSchedule.objects.create(source=source, account=source.account, frequency=frequency, is_enabled=True, periodic_task=pt)
        logger.info("Created schedule for source %s, runs %s", source.pk, frequency)
        return schedule, True

def disable_source_schedule(source: Source) -> None:
    """Pause a source's schedule without deleting it — disables both the SourceSchedule and its PeriodicTask. No-op if the source has no schedule."""
    try:
        schedule = source.schedule
    except SourceSchedule.DoesNotExist:
        return
    schedule.is_enabled = False
    if schedule.periodic_task:
        schedule.periodic_task.enabled = False
        schedule.periodic_task.save()
    schedule.save()
    logger.info("Paused schedule for source %s, was running %s", source.pk, schedule.frequency)

def delete_source_schedule(source: Source) -> None:
    """Remove a source's schedule entirely, deleting its PeriodicTask first. No-op if the source has no schedule."""
    try:
        schedule = source.schedule
    except SourceSchedule.DoesNotExist:
        return
    if schedule.periodic_task:
        schedule.periodic_task.delete()
    schedule.delete()
    logger.info("Deleted schedule for source %s, was running %s", source.pk, schedule.frequency)

def toggle_source_schedule(source: Source) -> tuple[SourceSchedule, bool]:
    """
    - Flip a source's schedule between enabled and paused (keeping the PeriodicTask in step) and return (schedule, was_paused).
    - was_paused reflects the state before the toggle, so callers can tell a resume from a pause (e.g. to kick off an immediate sync on resume). Assumes a schedule exists.
    """
    schedule = source.schedule
    was_paused = not schedule.is_enabled
    schedule.is_enabled = not schedule.is_enabled
    schedule.save()
    if was_paused:
        logger.info("Resumed schedule for source %s, runs %s", source.pk, schedule.frequency)
    else:
        logger.info("Paused schedule for source %s, was running %s", source.pk, schedule.frequency)
    if schedule.periodic_task:
        schedule.periodic_task.enabled = schedule.is_enabled
        schedule.periodic_task.save()
    return schedule, was_paused
