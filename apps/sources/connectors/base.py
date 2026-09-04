""" Defines the connector interface every data source implements. Concrete connectors (PostgreSQL, Airbyte, demo) are selected by connectors.registry and consumed uniformly by the sync task. """
from __future__ import annotations

from abc import ABC, abstractmethod
from typing import Any


class BaseConnector(ABC):
    """
    - Abstract base every source connector implements, so the sync pipeline treats native, Airbyte-backed, and demo sources identically.
    - Constructed with the source's decrypted credentials dict; subclasses use it to reach the source.
    """
    def __init__(self, credentials: dict[str, Any]) -> None:
        self.credentials = credentials

    @abstractmethod
    def test_connection(self) -> bool:
        """Return True if the source is reachable with the given credentials, False otherwise (never raise)."""
        ...

    @abstractmethod
    def discover_catalog(self) -> list[dict[str, Any]]:
        """Return the source's structure as a list of schema dicts: [{'name', 'tables': [{'name', 'table_type', 'columns': [{'name', 'data_type', 'nullable', 'primary_key'}]}]}]."""
        ...

    @abstractmethod
    def get_table_metadata(self, schema_name: str, table_name: str) -> dict[str, Any]:
        """Return per-table stats as {'row_count': int | None, 'column_stats': dict}. Connectors without a stats catalog (e.g. Airbyte) return None/empty."""
        ...