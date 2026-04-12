from __future__ import annotations

from typing import Type

from .base import BaseConnector
from .postgresql import PostgreSQLConnector
from demo.connectors.demo_connector import DemoConnector

_REGISTRY: dict[str, Type[BaseConnector]] = {
    'postgresql': PostgreSQLConnector,
    'hubspot_demo': DemoConnector,
    'ga_demo': DemoConnector,
    'customerdb_demo': DemoConnector,
}


def get_connector(source_type_name: str) -> Type[BaseConnector]:
    try:
        return _REGISTRY[source_type_name]
    except KeyError:
        raise ValueError(f"No connector registered for source type: {source_type_name}")