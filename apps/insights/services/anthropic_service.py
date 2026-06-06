from __future__ import annotations

import anthropic
import json

from openai.types.responses import response

from apps.catalog.models import Table
from apps.sources.models import Source
from .base import BaseService
from apps.insights.prompts.table_insights import ANTHROPIC_TABLE_DESCRIPTION_MODEL, build_table_description_prompt, TABLE_DESCRIPTION_SYSTEM_MESSAGE, TABLE_DESCRIPTION_MAX_TOKENS
from apps.insights.prompts.source_insights import ANTHROPIC_SOURCE_OVERVIEW_MODEL, SOURCE_OVERVIEW_SYSTEM_MESSAGE, SOURCE_OVERVIEW_MAX_TOKENS, build_source_overview_prompt
from apps.insights.prompts.intra_source_use_cases import ANTHROPIC_USE_CASE_MODEL, build_use_case_suggestions_prompt, USE_CASE_MAX_TOKENS, USE_CASE_SYSTEM_MESSAGE
from apps.insights.prompts.cross_source_discovery import ANTHROPIC_RELATIONSHIP_DISCOVERY_MODEL, build_relationship_discovery_prompt, RELATIONSHIP_DISCOVERY_SYSTEM_MESSAGE, \
    RELATIONSHIP_DISCOVERY_MAX_TOKENS, build_hypothesis_prompt, ANTHROPIC_HYPOTHESIS_MODEL, HYPOTHESIS_MAX_TOKENS, HYPOTHESIS_SYSTEM_MESSAGE, build_cross_source_use_case_prompt, \
    ANTHROPIC_CROSS_SOURCE_USE_CASE_MODEL, CROSS_SOURCE_USE_CASE_MAX_TOKENS, CROSS_SOURCE_USE_CASE_SYSTEM_MESSAGE


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

    def generate_intra_source_use_case(self, source: Source) -> list[dict]:
        prompt = build_use_case_suggestions_prompt(source)
        response = self.client.messages.create(
            model=ANTHROPIC_USE_CASE_MODEL,
            max_tokens=USE_CASE_MAX_TOKENS,
            system=USE_CASE_SYSTEM_MESSAGE,
            messages=[ # type: ignore
                {"role": "user", "content": prompt},
            ],
        )
        raw = response.content[0].text.strip()
        if raw.startswith("```"):
            raw = raw.split("\n", 1)[1]
            raw = raw.rsplit("```", 1)[0]
        result = json.loads(raw.strip())
        return result['use_cases']

    def discover_cross_source_relationships(self, source_a: Source, source_b: Source) -> dict:
        prompt = build_relationship_discovery_prompt(source_a, source_b)
        response = self.client.messages.create(
            model=ANTHROPIC_RELATIONSHIP_DISCOVERY_MODEL,
            max_tokens=RELATIONSHIP_DISCOVERY_MAX_TOKENS,
            system=RELATIONSHIP_DISCOVERY_SYSTEM_MESSAGE,
            messages=[ # type: ignore
                {"role": "user", "content": prompt},
            ],
        )
        raw = response.content[0].text.strip()
        if raw.startswith("```"):
            raw = raw.split("\n", 1)[1]
            raw = raw.rsplit("```", 1)[0]
        result = json.loads(raw.strip())
        return result

    def generate_cross_source_hypotheses(self, relationship: dict, source_a: Source, source_b: Source) -> list[dict]:
        prompt = build_hypothesis_prompt(relationship, source_a, source_b)
        response = self.client.messages.create(
            model=ANTHROPIC_HYPOTHESIS_MODEL,
            max_tokens=HYPOTHESIS_MAX_TOKENS,
            system=HYPOTHESIS_SYSTEM_MESSAGE,
            messages=[ # type: ignore
                {"role": "user", "content": prompt},
            ],
        )
        raw = response.content[0].text.strip()
        if raw.startswith("```"):
            raw = raw.split("\n", 1)[1]
            raw = raw.rsplit("```", 1)[0]
        result = json.loads(raw.strip())
        return result['hypotheses']

    def generate_cross_source_use_case(self, hypothesis: dict, source_a: Source, source_b: Source) -> dict:
        prompt = build_cross_source_use_case_prompt(hypothesis, source_a, source_b)
        response = self.client.messages.create(
            model=ANTHROPIC_CROSS_SOURCE_USE_CASE_MODEL,
            max_tokens=CROSS_SOURCE_USE_CASE_MAX_TOKENS,
            system=CROSS_SOURCE_USE_CASE_SYSTEM_MESSAGE,
            messages=[ # type: ignore
                {"role": "user", "content": prompt},
            ],
        )
        raw = response.content[0].text.strip()
        if raw.startswith("```"):
            raw = raw.split("\n", 1)[1]
            raw = raw.rsplit("```", 1)[0]
        result = json.loads(raw.strip())
        return result
