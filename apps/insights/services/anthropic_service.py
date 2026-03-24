from __future__ import annotations

import anthropic

from apps.catalog.models import Table
from .base import BaseService
from apps.insights.prompts.table_insights import ANTHROPIC_TABLE_DESCRIPTION_MODEL, build_table_description_prompt, TABLE_DESCRIPTION_SYSTEM_MESSAGE, TABLE_DESCRIPTION_MAX_TOKENS


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