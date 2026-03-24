from __future__ import annotations

from openai import OpenAI

from apps.catalog.models import Table
from apps.insights.prompts.table_insights import build_table_description_prompt, TABLE_DESCRIPTION_SYSTEM_MESSAGE, OPENAI_TABLE_DESCRIPTION_MODEL, TABLE_DESCRIPTION_MAX_TOKENS
from .base import BaseService


class OpenAIService(BaseService):
    def __init__(self, api_key: str) -> None:
        super().__init__(api_key)
        self.client = OpenAI(api_key=self.api_key)

    def generate_table_description(self, table: Table) -> str:
        prompt = build_table_description_prompt(table)
        response = self.client.chat.completions.create(
            model = OPENAI_TABLE_DESCRIPTION_MODEL,
            messages = [ # type: ignore
                {"role": "system", "content": TABLE_DESCRIPTION_SYSTEM_MESSAGE},
                {"role": "user", "content": prompt},
            ],
            max_tokens = TABLE_DESCRIPTION_MAX_TOKENS,
        )
        return response.choices[0].message.content.strip()