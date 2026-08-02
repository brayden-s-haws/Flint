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
    name = models.CharField(max_length=255)
    airbyte_connector_name = models.CharField(max_length=255, blank=True)
    is_demo = models.BooleanField(default=False)

    def __str__(self) -> str:
        return self.name

class Source(TenantAwareModel):
    source_type = models.ForeignKey(SourceType, on_delete=models.CASCADE)
    name = models.CharField(max_length=255)
    credentials = models.TextField()
    first_synced_at = models.DateTimeField(null=True, blank=True)

    def __str__(self) -> str:
        return self.name

class SourceSyncLog(TenantAwareModel):
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
    source = models.OneToOneField(Source, on_delete=models.CASCADE, related_name='schedule')
    frequency = models.CharField(max_length=255, choices=FREQUENCY_CHOICES)
    is_enabled = models.BooleanField(default=True)
    periodic_task = models.OneToOneField('django_celery_beat.PeriodicTask', on_delete=models.SET_NULL, null=True, blank=True)

    def __str__(self) -> str:
        return f"{self.frequency} schedule for {self.source.name}"

    @property
    def cron_expression(self) -> str | None:
        if not self.periodic_task:
            return None
        ct = self.periodic_task.crontab
        if not ct:
            return None
        return f"{ct.minute} {ct.hour} {ct.day_of_month} {ct.month_of_year} {ct.day_of_week}"