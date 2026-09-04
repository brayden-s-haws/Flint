""" Defines the provider-agnostic interface for LLM insight generation. Concrete subclasses (OpenAIService, AnthropicService) wrap a specific provider's SDK; callers select one through get_service() in provider.py and never depend on a provider directly. """
from __future__ import annotations

from abc import ABC, abstractmethod

from apps.catalog.models import Table
from apps.sources.models import Source

class BaseService(ABC):
    """
    - Abstract base every LLM provider implements, giving the rest of the app one uniform way to generate insights regardless of provider.
    - Each method follows the same shape: build the prompt (from apps/insights/prompts/), call the provider with that stage's model/system-message/max-tokens config, then return native Python — prose as a str, structured output parsed out of the model's JSON.
    - Constructed with the provider's API key; concrete subclasses use it to build their SDK client.
    """
    def __init__(self, api_key: str) -> None:
        self.api_key = api_key

    @abstractmethod
    def generate_table_description(self, table: Table) -> str:
        """Return a markdown prose description of a single table."""
        ...

    @abstractmethod
    def generate_source_overview(self, source: Source) -> str:
        """Return a markdown prose overview of a whole source."""
        ...

    @abstractmethod
    def generate_intra_source_use_case(self, source: Source) -> list[dict]:
        """Return a list of intra-source use-case dicts (title, description, tables, starter_sql) derived from one source's schema."""
        ...

    @abstractmethod
    def discover_cross_source_relationships(self, source_a: Source, source_b: Source) -> dict:
        """Return the discovered relationships between two sources: join opportunities and semantic overlaps. Stage 1 of the cross-source pipeline."""
        ...

    @abstractmethod
    def generate_cross_source_hypotheses(self, relationship: dict, source_a: Source, source_b: Source) -> list[dict]:
        """Return a list of analytical hypothesis dicts (each with a specificity_score) for one discovered relationship. Stage 2 of the cross-source pipeline."""
        ...

    @abstractmethod
    def generate_cross_source_use_case(self, hypothesis: dict, source_a: Source, source_b: Source) -> dict:
        """Return the final user-facing cross-source insight dict (title, description, business_value, starter_sql) for one hypothesis. Stage 3 of the cross-source pipeline."""
        ...