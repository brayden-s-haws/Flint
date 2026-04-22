from __future__ import annotations

from django.db import models
from apps.core.models import TenantAwareModel
from django.contrib.contenttypes.models import ContentType
from django.contrib.contenttypes.fields import GenericForeignKey

class Insight(TenantAwareModel):
    text = models.TextField()
    insight_type = models.CharField(max_length=255, choices=[
        ('ai', 'AI Generated'),
        ('manual', 'Manual'),
        ('use_case_suggestion', 'Use Case Suggestion'),
    ])
    status = models.CharField(max_length=255, choices=[
        ('active', 'Active'),
        ('archived', 'Archived'),
        ('deleted', 'Deleted'),
    ])
    insight_prompt = models.ForeignKey('InsightPrompt', on_delete=models.SET_NULL, null=True)
    structured_data = models.JSONField(null=True, blank=True)
    rating = models.CharField(max_length=20, choices=[
        ('none', 'None'),
        ('approved', 'Approved'),
        ('rejected', 'Rejected'),
    ], default='none')

    def __str__(self) -> str:
        return f"{self.insight_type}"


class InsightTarget(TenantAwareModel):
    insight = models.ForeignKey(Insight, on_delete=models.CASCADE)
    content_type = models.ForeignKey(ContentType, on_delete=models.CASCADE)
    object_id = models.PositiveIntegerField()
    target = GenericForeignKey('content_type', 'object_id')

    def __str__(self) -> str:
        return f"{self.insight} -> {self.target}"


class InsightPrompt(TenantAwareModel):
    name = models.CharField(max_length=255)
    prompt = models.TextField()
    version = models.IntegerField(default=1)
    provider = models.CharField(
        max_length=255,
        choices=[
            ('openai', 'OpenAI'),
            ('anthropic', 'Anthropic'),
        ],
        default = 'openai',
    )

    def __str__(self) -> str:
        return f"{self.name} -> {self.prompt}"