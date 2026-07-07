from __future__ import annotations

from openai import OpenAI
import json

from apps.catalog.models import Table
from apps.sources.models import Source
from apps.insights.prompts.table_insights import build_table_description_prompt, TABLE_DESCRIPTION_SYSTEM_MESSAGE, OPENAI_TABLE_DESCRIPTION_MODEL, TABLE_DESCRIPTION_MAX_TOKENS
from apps.insights.prompts.source_insights import OPENAI_SOURCE_OVERVIEW_MODEL, SOURCE_OVERVIEW_SYSTEM_MESSAGE, SOURCE_OVERVIEW_MAX_TOKENS, build_source_overview_prompt
from apps.insights.prompts.intra_source_use_cases import USE_CASE_SYSTEM_MESSAGE, build_use_case_suggestions_prompt, USE_CASE_MAX_TOKENS, OPENAI_USE_CASE_MODEL
from apps.insights.prompts.cross_source_discovery import (
    OPENAI_RELATIONSHIP_DISCOVERY_MODEL, RELATIONSHIP_DISCOVERY_SYSTEM_MESSAGE, RELATIONSHIP_DISCOVERY_MAX_TOKENS, build_relationship_discovery_prompt,
    OPENAI_HYPOTHESIS_MODEL, HYPOTHESIS_SYSTEM_MESSAGE, HYPOTHESIS_MAX_TOKENS, build_hypothesis_prompt,
    OPENAI_CROSS_SOURCE_USE_CASE_MODEL, CROSS_SOURCE_USE_CASE_SYSTEM_MESSAGE, CROSS_SOURCE_USE_CASE_MAX_TOKENS, build_cross_source_use_case_prompt,
)
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

    def discover_cross_source_relationships(self, source_a: Source, source_b: Source) -> dict:
        prompt = build_relationship_discovery_prompt(source_a, source_b)
        response = self.client.chat.completions.create(
            model=OPENAI_RELATIONSHIP_DISCOVERY_MODEL,
            messages=[ # type: ignore
                {"role": "system", "content": RELATIONSHIP_DISCOVERY_SYSTEM_MESSAGE},
                {"role": "user", "content": prompt},
            ],
            max_tokens=RELATIONSHIP_DISCOVERY_MAX_TOKENS,
        )
        raw = response.choices[0].message.content.strip()
        if raw.startswith("```"):
            raw = raw.split("\n", 1)[1]
            raw = raw.rsplit("```", 1)[0]
        result = json.loads(raw.strip())
        return result

    def generate_cross_source_hypotheses(self, relationship: dict, source_a: Source, source_b: Source) -> list[dict]:
        prompt = build_hypothesis_prompt(relationship, source_a, source_b)
        response = self.client.chat.completions.create(
            model=OPENAI_HYPOTHESIS_MODEL,
            messages=[ # type: ignore
                {"role": "system", "content": HYPOTHESIS_SYSTEM_MESSAGE},
                {"role": "user", "content": prompt},
            ],
            max_tokens=HYPOTHESIS_MAX_TOKENS,
        )
        raw = response.choices[0].message.content.strip()
        if raw.startswith("```"):
            raw = raw.split("\n", 1)[1]
            raw = raw.rsplit("```", 1)[0]
        result = json.loads(raw.strip())
        return result['hypotheses']

    def generate_cross_source_use_case(self, hypothesis: dict, source_a: Source, source_b: Source) -> dict:
        prompt = build_cross_source_use_case_prompt(hypothesis, source_a, source_b)
        response = self.client.chat.completions.create(
            model=OPENAI_CROSS_SOURCE_USE_CASE_MODEL,
            messages=[ # type: ignore
                {"role": "system", "content": CROSS_SOURCE_USE_CASE_SYSTEM_MESSAGE},
                {"role": "user", "content": prompt},
            ],
            max_tokens=CROSS_SOURCE_USE_CASE_MAX_TOKENS,
        )
        raw = response.choices[0].message.content.strip()
        if raw.startswith("```"):
            raw = raw.split("\n", 1)[1]
            raw = raw.rsplit("```", 1)[0]
        result = json.loads(raw.strip())
        return result
