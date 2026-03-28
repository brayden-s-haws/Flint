from __future__ import annotations

import anthropic

from apps.catalog.models import Table
from apps.sources.models import Source
from .base import BaseService
from apps.insights.prompts.table_insights import ANTHROPIC_TABLE_DESCRIPTION_MODEL, build_table_description_prompt, TABLE_DESCRIPTION_SYSTEM_MESSAGE, TABLE_DESCRIPTION_MAX_TOKENS
from apps.insights.prompts.source_insights import ANTHROPIC_SOURCE_OVERVIEW_MODEL, SOURCE_OVERVIEW_SYSTEM_MESSAGE, SOURCE_OVERVIEW_MAX_TOKENS, build_source_overview_prompt


class AnthropicService(BaseService):
    def __init__(self, api_key: str) -> None:
        super().__init__(api_key)
        self.client = anthropic.Anthropic(api_key=self.api_key)

    def generate_table_description(self, table: Table) -> str:
        prompt = build_table_description_prompt(table)
        response = self.client.messages.create(
            model=ANTHROPIC_TABLE_DESCRIPTION_MODEL,
            max_tokens=TABLE_DESCRIPTION_MAX_TOKENS,
            system=TABLE_DESCRIPTION_SYSTEM_MESSAGE,
            messages=[ # type: ignore
                {"role": "user", "content": prompt},
            ],
        )
        return response.content[0].text.strip()

    def generate_source_overview(self, source: Source) -> str:
        prompt = build_source_overview_prompt(source)
        response = self.client.messages.create(
            model=ANTHROPIC_SOURCE_OVERVIEW_MODEL,
            max_tokens=SOURCE_OVERVIEW_MAX_TOKENS,
            system=SOURCE_OVERVIEW_SYSTEM_MESSAGE,
            messages=[ # type: ignore
                {"role": "user", "content": prompt},
            ],
        )
        return response.content[0].text.strip()