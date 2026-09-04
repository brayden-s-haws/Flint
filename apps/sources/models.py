""" Models for connected data sources: the source-type catalog, per-account source connections, their sync history, and their sync schedules. """
from __future__ import annotations

from django.db import models

from apps.core.models import TenantAwareModel, TimeStampedModel

FREQUENCY_CHOICES = [
        ('hourly', 'Hourly'),
        ('daily', 'Daily'),
        ('weekly', 'Weekly'),
        ('monthly', 'Monthly'),
    ]

class SourceType(TimeStampedModel):
    """
    - A kind of source a user can connect (PostgreSQL, Stripe, HubSpot, etc.), seeded via data migrations, not tenant-scoped (shared across all accounts).
    - `airbyte_connector_name` set means this type routes through the Airbyte adapter (see connectors.registry.build_connector); blank means a native connector keyed by `name`.
    - `config_example` is the placeholder JSON shown on the connect form for Airbyte types; `is_demo` marks the built-in demo sources.
    """
    name = models.CharField(max_length=255)
    airbyte_connector_name = models.CharField(max_length=255, blank=True)
    config_example = models.TextField(blank=True)
    is_demo = models.BooleanField(default=False)

    def __str__(self) -> str:
        return self.name

class Source(TenantAwareModel):
    """
    - An account's connection to one data source instance.
    - `credentials` holds the Fernet-encrypted connection details (never plaintext); decrypt only at connector instantiation via encryption.decrypt_credentials.
    - `first_synced_at` gates features that require synced data (e.g. cross-source discovery); null until the first successful sync.
    """
    source_type = models.ForeignKey(SourceType, on_delete=models.CASCADE)
    name = models.CharField(max_length=255)
    credentials = models.TextField()
    first_synced_at = models.DateTimeField(null=True, blank=True)

    def __str__(self) -> str:
        return self.name

class SourceSyncLog(TenantAwareModel):
    """
    - One row per sync attempt, recording status (running/success/failed), timing, records synced, and any error message. Drives the sync-history UI and the "last synced" display.
    """
    source = models.ForeignKey(Source, on_delete=models.CASCADE)
    status = models.CharField(max_length=255, choices=[
        ('success', 'Success'),
        ('failed', 'Failed'),
        ('running', 'Running'),
    ])
    started_at = models.DateTimeField()
    completed_at = models.DateTimeField(null=True, blank=True)
    records_synced = models.IntegerField(default=0)
    error_message = models.TextField(null=True, blank=True)

    def __str__(self) -> str:
        return f"Sync Log for {self.source}"

class SourceSchedule(TenantAwareModel):
    """
    - Optional automated sync schedule for a source (one-to-one). `frequency` is the user-facing cadence; the actual scheduling is backed by a django_celery_beat PeriodicTask.
    - `is_enabled` pauses the schedule without deleting it. The linked `periodic_task` is created/updated/removed by the helpers in scheduling.py and cleaned up by a post_delete signal.
    """
    source = models.OneToOneField(Source, on_delete=models.CASCADE, related_name='schedule')
    frequency = models.CharField(max_length=255, choices=FREQUENCY_CHOICES)
    is_enabled = models.BooleanField(default=True)
    periodic_task = models.OneToOneField('django_celery_beat.PeriodicTask', on_delete=models.SET_NULL, null=True, blank=True)

    def __str__(self) -> str:
        return f"{self.frequency} schedule for {self.source.name}"

    @property
    def cron_expression(self) -> str | None:
        """Return the linked periodic task's crontab as a standard 5-field cron string, or None if no task/crontab is set."""
        if not self.periodic_task:
            return None
        ct = self.periodic_task.crontab
        if not ct:
            return None
        return f"{ct.minute} {ct.hour} {ct.day_of_month} {ct.month_of_year} {ct.day_of_week}"