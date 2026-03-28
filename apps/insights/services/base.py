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