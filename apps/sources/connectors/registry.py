""" Maps a SourceType to its connector implementation. build_connector is the single entry point callers use to obtain a ready connector without knowing whether the source is native, Airbyte-backed, or demo. """
from __future__ import annotations

from typing import Type, Any, TYPE_CHECKING

from .base import BaseConnector
from .postgresql import PostgreSQLConnector
from demo.connectors.demo_connector import DemoConnector

if TYPE_CHECKING:
    from apps.sources.models import SourceType


# Native/demo connectors keyed by SourceType.name. Airbyte-backed types are not listed here — they route by airbyte_connector_name in build_connector.
_REGISTRY: dict[str, Type[BaseConnector]] = {
    'PostgreSQL': PostgreSQLConnector,
    'HubSpot (Demo)': DemoConnector,
    'Google Analytics (Demo)': DemoConnector,
    'Customer Database (Demo)': DemoConnector,
}


def get_connector(source_type_name: str) -> Type[BaseConnector]:
    """Return the connector class registered for a native/demo source type name; raises ValueError if none is registered."""
    try:
        return _REGISTRY[source_type_name]
    except KeyError:
        raise ValueError(f"No connector registered for source type: {source_type_name}")


def build_connector(source_type: SourceType, credentials: dict[str, Any]) -> BaseConnector:
    """
    - Return a connector instance for a source type, wired with its credentials.
    - Airbyte routing takes priority: any type with an `airbyte_connector_name` builds an AirbyteConnector (imported lazily to avoid importing PyAirbyte unless needed); otherwise falls back to the native/demo class from the registry.
    """
    if source_type.airbyte_connector_name:
        from .airbyte import AirbyteConnector
        return AirbyteConnector(credentials, source_type.airbyte_connector_name)
    return get_connector(source_type.name)(credentials)