""" Models AI generated content throughout the system. The terminology of 'Insights' is used to refer to AI-generated content, including use cases, descriptions, and other types of insights. All
insights are associated with one or more target objects. Prompts that are used to generate insights are stored for future reference and auditability. """
from __future__ import annotations

from django.db import models
from apps.core.models import TenantAwareModel
from django.contrib.contenttypes.models import ContentType
from django.contrib.contenttypes.fields import GenericForeignKey

class Insight(TenantAwareModel):
    """
    - Insights are the various types of AI-generated content in the system.
    - For each insight, the type, status, and user rating are tracked.
    - Prose-based insights like descriptions are stored as text, while structured insights like use cases are stored as structured data (JSON).
    - Status lifecycle handles both the ai-generation process and user interaction with insights.
    """
    text = models.TextField()
    insight_type = models.CharField(max_length=255, choices=[
        ('ai', 'AI Generated'),
        ('table_description', 'Table Description'),
        ('source_overview', 'Source Overview'),
        ('use_case_suggestion', 'Use Case Suggestion'),
        ('cross_source_use_case', 'Cross Source Use Case'),
        ('manual', 'Manual'),
    ])
    status = models.CharField(max_length=255, choices=[
        ('pending', 'Pending'),
        ('pending_review', 'Pending Review'),
        ('active', 'Active'),
        ('dismissed', 'Dismissed'),
        ('failed', 'Failed'),
        ('archived', 'Archived'),
        ('deleted', 'Deleted'),
    ])
    insight_prompt = models.ForeignKey('InsightPrompt', on_delete=models.SET_NULL, null=True, blank=True)
    structured_data = models.JSONField(null=True, blank=True)
    rating = models.CharField(max_length=20, choices=[
        ('none', 'None'),
        ('approved', 'Approved'),
        ('rejected', 'Rejected'),
    ], default='none')

    def __str__(self) -> str:
        return f"{self.insight_type}"


class InsightTarget(TenantAwareModel):
    """
    - Insights are associated with a target object, such as a table or source, via a generic foreign key.
    - A single insight can be associated with multiple target objects, as is the case with cross-source insights.
    - When an insight is deleted, its associated target links are also deleted, the target objects themselves are not affected.
    """
    insight = models.ForeignKey(Insight, on_delete=models.CASCADE)
    content_type = models.ForeignKey(ContentType, on_delete=models.CASCADE)
    object_id = models.PositiveIntegerField()
    target = GenericForeignKey('content_type', 'object_id')

    def __str__(self) -> str:
        return f"{self.insight} -> {self.target}"


class InsightPrompt(TenantAwareModel):
    """
    - Insight generation requires different prompts per use case, which can be updated over time. We track the version and provider of each prompt for future reference.
    - For system-managed insight generation all prompts are stored as constants in their respective prompts file.
    """
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