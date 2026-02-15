from __future__ import annotations

from django.db import models
from apps.core.models import TenantAwareModel, TimeStampedModel


class SourceType(TimeStampedModel):
    name = models.CharField(max_length=255)

    def __str__(self) -> str:
        return self.name

class Source(TenantAwareModel):
    source_type = models.ForeignKey(SourceType, on_delete=models.CASCADE)
    name = models.CharField(max_length=255)
    credentials = models.TextField()
    first_synced_at = models.DateTimeField(null=True)

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
    completed_at = models.DateTimeField(null=True)
    records_synced = models.IntegerField(default=0)
    error_message = models.TextField(null=True)


    def __str__(self) -> str:
        return f"Sync Log for {self.source}"