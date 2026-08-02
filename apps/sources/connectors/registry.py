from __future__ import annotations

from typing import Type, Any, TYPE_CHECKING

from .base import BaseConnector
from .postgresql import PostgreSQLConnector
from demo.connectors.demo_connector import DemoConnector

if TYPE_CHECKING:
    from apps.sources.models import SourceType


_REGISTRY: dict[str, Type[BaseConnector]] = {
    'PostgreSQL': PostgreSQLConnector,
    'HubSpot (Demo)': DemoConnector,
    'Google Analytics (Demo)': DemoConnector,
    'Customer Database (Demo)': DemoConnector,
}


def get_connector(source_type_name: str) -> Type[BaseConnector]:
    try:
        return _REGISTRY[source_type_name]
    except KeyError:
        raise ValueError(f"No connector registered for source type: {source_type_name}")


def build_connector(source_type: SourceType, credentials: dict[str, Any]) -> BaseConnector:
    if source_type.airbyte_connector_name:
        from .airbyte import AirbyteConnector
        return AirbyteConnector(credentials, source_type.airbyte_connector_name)
    return get_connector(source_type.name)(credentials)