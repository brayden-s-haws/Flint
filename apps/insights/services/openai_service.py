from __future__ import annotations

from openai import OpenAI
import json

from apps.catalog.models import Table
from apps.sources.models import Source
from apps.insights.prompts.table_insights import build_table_description_prompt, TABLE_DESCRIPTION_SYSTEM_MESSAGE, OPENAI_TABLE_DESCRIPTION_MODEL, TABLE_DESCRIPTION_MAX_TOKENS
from apps.insights.prompts.source_insights import OPENAI_SOURCE_OVERVIEW_MODEL, SOURCE_OVERVIEW_SYSTEM_MESSAGE, SOURCE_OVERVIEW_MAX_TOKENS, build_source_overview_prompt
from apps.insights.prompts.intra_source_use_cases import USE_CASE_SYSTEM_MESSAGE, build_use_case_suggestions_prompt, USE_CASE_MAX_TOKENS, OPENAI_USE_CASE_MODEL
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

    def generate_source_overview(self, source: Source) -> str:
        prompt = build_source_overview_prompt(source)
        response = self.client.chat.completions.create(
            model=OPENAI_SOURCE_OVERVIEW_MODEL,
            messages=[ # type: ignore
                {"role": "system", "content": SOURCE_OVERVIEW_SYSTEM_MESSAGE},
                {"role": "user", "content": prompt},
            ],
            max_tokens=SOURCE_OVERVIEW_MAX_TOKENS,
        )
        return response.choices[0].message.content.strip()

    def generate_intra_source_use_case(self, source: Source) -> list[dict]:
        prompt = build_use_case_suggestions_prompt(source)
        response = self.client.chat.completions.create(
            model=OPENAI_USE_CASE_MODEL,
            messages=[ # type: ignore
                {"role": "system", "content": USE_CASE_SYSTEM_MESSAGE},
                {"role": "user", "content": prompt},
            ],
            max_tokens=USE_CASE_MAX_TOKENS,
        )
        result = json.loads(response.choices[0].message.content.strip())
        return result['use_cases']
