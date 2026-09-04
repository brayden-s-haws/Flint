""" Provider selection for insight generation. get_service() is the single seam callers use to obtain a BaseService, keeping the rest of the app decoupled from any specific LLM provider. """
from __future__ import annotations

from django.conf import settings

from .base import BaseService
from .openai_service import OpenAIService
from .anthropic_service import AnthropicService


def get_service(provider: str) -> BaseService:
    """
    - Returns a concrete BaseService for the named provider ('openai' or 'anthropic'), wired with that provider's API key from settings.
    - Raises ValueError for an unknown provider name.
    """
    if provider == 'openai':
        api_key = settings.OPENAI_API_KEY
        return OpenAIService(api_key=api_key)
    elif provider == 'anthropic':
        api_key = settings.ANTHROPIC_API_KEY
        return AnthropicService(api_key=api_key)
    else:
        raise ValueError(f"Unknown provider: {provider}")
