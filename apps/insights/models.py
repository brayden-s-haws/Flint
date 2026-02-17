from __future__ import annotations

from django.db import models
from apps.core.models import TenantAwareModel

class Insight(TenantAwareModel):
    text = models.TextField()
    insight_type = models.CharField(max_length=255, choices=[
        ('ai', 'AI Generated'),
        ('manual', 'Manual'),
    ])
    status = models.CharField(max_length=255, choices=[
        ('active', 'Active'),
        ('archived', 'Archived'),
        ('deleted', 'Deleted'),
    ])
    insight_prompt = models.ForeignKey('InsightPrompt', on_delete=models.SET_NULL, null=True)

    def __str__(self) -> str:
        return f"{self.insight_type}"

class InsightTarget(TenantAwareModel):
    insight = models.ForeignKey(Insight, on_delete=models.CASCADE)
    target = models.ForeignKey('catalog.Table', on_delete=models.CASCADE)

    def __str__(self) -> str:
        return f"{self.insight} -> {self.target}"

class InsightPrompt(TenantAwareModel):
    name = models.CharField(max_length=255)
    prompt = models.TextField()
    version = models.IntegerField(default=1)

    def __str__(self) -> str:
        return f"{self.name} -> {self.prompt}"