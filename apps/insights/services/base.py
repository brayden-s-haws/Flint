from __future__ import annotations

from abc import ABC, abstractmethod

from apps.catalog.models import Table

class BaseService(ABC):
    def __init__(self, api_key: str) -> None:
        self.api_key = api_key

    @abstractmethod
    def generate_table_description(self, table: Table) -> str:
        ...