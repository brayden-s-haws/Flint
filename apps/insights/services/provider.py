from __future__ import annotations

from django.conf import settings

from .base import BaseService
from .openai_service import OpenAIService
from .anthropic_service import AnthropicService


def get_service(provider: str) -> BaseService:
    if provider == 'openai':
        api_key = settings.OPENAI_API_KEY
        return OpenAIService(api_key=api_key)
    elif provider == 'anthropic':
        api_key = settings.ANTHROPIC_API_KEY
        return AnthropicService(api_key=api_key)
    else:
        raise ValueError(f"Unknown provider: {provider}")
