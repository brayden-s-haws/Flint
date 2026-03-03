from __future__ import annotations

from abc import ABC, abstractmethod
from typing import Any


class BaseConnector(ABC):
    def __init__(self, credentials: dict[str, Any]) -> None:
        self.credentials = credentials

    @abstractmethod
    def test_connection(self) -> bool:
        ...

    @abstractmethod
    def discover_catalog(self) -> list[dict[str, Any]]:
        ...