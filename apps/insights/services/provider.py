from __future__ import annotations

# TODO(stub): Import django.conf.settings — used to read OPENAI_API_KEY and ANTHROPIC_API_KEY
# TODO(stub): Import InsightPrompt from apps.insights.models
# TODO(stub): Import BaseService from .base
# TODO(stub): Import OpenAIService from .openai_service
# TODO(stub): Import AnthropicService from .anthropic_service


# TODO(stub): Define get_service(insight_prompt: InsightPrompt) -> BaseService
# This function mirrors the connector registry pattern in apps/sources/connectors/registry.py
# but instead of a dict lookup, use an if/elif on insight_prompt.provider since there are
# only two providers and the logic differs slightly (different settings keys).
#
# Steps:
# 1. Check insight_prompt.provider:
#    - if 'openai':
#        api_key = settings.OPENAI_API_KEY
#        return OpenAIService(api_key=api_key)
#    - elif 'anthropic':
#        api_key = settings.ANTHROPIC_API_KEY
#        return AnthropicService(api_key=api_key)
#    - else:
#        raise ValueError(f"Unknown provider: {insight_prompt.provider}")
#
# 2. Make sure OPENAI_API_KEY and ANTHROPIC_API_KEY are defined in settings.py,
#    read from the .env file via os.getenv(). Add them to .env.example too.
#
# Type hint: def get_service(insight_prompt: InsightPrompt) -> BaseService
def get_service():
    pass