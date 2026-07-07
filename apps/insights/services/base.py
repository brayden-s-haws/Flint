from __future__ import annotations

from abc import ABC, abstractmethod

from apps.catalog.models import Table
from apps.sources.models import Source

class BaseService(ABC):
    def __init__(self, api_key: str) -> None:
        self.api_key = api_key

    @abstractmethod
    def generate_table_description(self, table: Table) -> str:
        ...

    @abstractmethod
    def generate_source_overview(self, source: Source) -> str:
        ...

    @abstractmethod
    def generate_intra_source_use_case(self, source: Source) -> list[dict]:
        ...

    @abstractmethod
    def discover_cross_source_relationships(self, source_a: Source, source_b: Source) -> dict:
        ...

    @abstractmethod
    def generate_cross_source_hypotheses(self, relationship: dict, source_a: Source, source_b: Source) -> list[dict]:
        ...

    @abstractmethod
    def generate_cross_source_use_case(self, hypothesis: dict, source_a: Source, source_b: Source) -> dict:
        ...