from __future__ import annotations

from django.db import models

class TimeStampedModel(models.Model):
    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)

    class Meta:
        abstract = True

class TenantAwareModel(TimeStampedModel):
    account = models.ForeignKey('accounts.Account', on_delete=models.CASCADE, related_name='%(class)ss')

    class Meta:
        abstract = True