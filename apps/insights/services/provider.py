from __future__ import annotations

from django.conf import settings

from apps.insights.models import InsightPrompt
from .base import BaseService
from .openai_service import OpenAIService
from .anthropic_service import AnthropicService


def get_service(insight_prompt: InsightPrompt) -> BaseService:
    if insight_prompt.provider == 'openai':
        api_key = settings.OPENAI_API_KEY
        return OpenAIService(api_key=api_key)
    elif insight_prompt.provider == 'anthropic':
        api_key = settings.ANTHROPIC_API_KEY
        return AnthropicService(api_key=api_key)
    else:
        raise ValueError(f"Unknown provider: {insight_prompt.provider}")
