from __future__ import annotations

from django.db import models
from apps.core.models import TenantAwareModel
from django.contrib.contenttypes.models import ContentType
from django.contrib.contenttypes.fields import GenericForeignKey

# TODO(review): ContentType is imported but only used as a FK target in the model field — the import is correct, but it is unused as a Python name at module scope. Consider removing it; Django resolves the FK via the string 'contenttypes.ContentType'. Alternatively keep it if you prefer explicit imports.
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

    # TODO(review): __str__ returns the full prompt text — this can be very long and clutters admin list views. Consider truncating: f"{self.name} (v{self.version})" or similar.
    def __str__(self) -> str:
        return f"{self.name} -> {self.prompt}"