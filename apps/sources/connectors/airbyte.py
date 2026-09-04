""" Adapter that exposes any PyAirbyte source (SaaS connectors) through the BaseConnector interface. Schema-only: it discovers streams and their fields but pulls no records and has no stats catalog. """
from __future__ import annotations

import logging
from typing import Any
import airbyte as ab

from .base import BaseConnector

logger = logging.getLogger(__name__)


# Maps Airbyte/JSON-schema types to the Postgres-style type strings the catalog stores, so Airbyte columns render consistently with native ones.
TYPE_MAP = {
    'string': 'character varying',
    'integer': 'bigint',
    'number': 'numeric',
    'boolean': 'boolean',
    'object': 'jsonb',
    'array': 'jsonb',
    'date': 'date',
    'timestamp_with_timezone': 'timestamp with time zone',
    'timestamp_without_timezone': 'timestamp without time zone',
    'time_with_timezone': 'time with time zone',
    'time_without_timezone': 'time without time zone',
}


class AirbyteConnector(BaseConnector):
    """
    - BaseConnector backed by a named PyAirbyte source; `credentials` is that connector's config dict and `connector_name` is its Airbyte name (e.g. 'source-stripe').
    - Maps Airbyte streams → tables and stream JSON-schema properties → columns. Schema-only, so get_table_metadata always returns empty stats.
    """

    def __init__(self, credentials: dict[str, Any], connector_name: str) -> None:
        super().__init__(credentials)
        self.connector_name = connector_name

    def _get_source(self) -> Any:
        """Instantiate the PyAirbyte source (installing the connector on first use). Re-applies credentials onto the executor's config to work around a PyAirbyte bug with custom-components connectors."""
        source = ab.get_source(self.connector_name, config=self.credentials, install_if_missing=True)
        # Needed based on how PyAirbyte handles connectors with custom components, this may be a bug in the PyAirbyte project but has not been fixed over several versions
        executor = getattr(source, "executor", None)
        if executor is not None and hasattr(executor, "_config_dict"):
            executor._config_dict = {**executor._config_dict, **self.credentials}
        return source

    def test_connection(self) -> bool:
        try:
            source = self._get_source()
            source.check()
            return True
        except Exception as e:
            try:
                return bool(source.discovered_catalog.streams) # Since we do not pull actual records, we treat catalog being discoverable as a successful connection
            except Exception:
                logger.error(f"AirbyteConnector test_connection failed: {e}")
                return False

    def discover_catalog(self) -> list[dict[str, Any]]:
        """Return a single synthetic schema (named after the connector) whose tables are the connector's streams and whose columns come from each stream's JSON schema, with primary keys flagged."""
        try:
            source = self._get_source()
            streams = source.discovered_catalog.streams
            schema = {'name': self.connector_name.removeprefix('source-'), 'tables': []}
            for stream in streams:
                pk_set = {col for group in (stream.source_defined_primary_key or []) for col in group}
                properties = stream.json_schema.get('properties', {})
                columns = [
                    {
                        'name': name,
                        'data_type': self._resolve_data_type(prop),
                        'nullable': self._is_nullable(prop),
                        'primary_key': name in pk_set,
                    }
                    for name, prop in properties.items()
                ]
                schema['tables'].append({'name': stream.name, 'table_type': 'BASE TABLE', 'columns': columns})
            return [schema]
        except Exception as e:
            logger.error(f"AirbyteConnector discover_catalog failed: {e}")
            return []


    @staticmethod
    def _resolve_data_type(prop: dict[str, Any]) -> str:
        if prop.get('airbyte_type'):
            key = prop.get('airbyte_type')
        else:
            t = prop.get('type')
            if isinstance(t, list):
                t = next((n for n in t if n != 'null'), 'string')
            if t == 'string':
                key = {'date': 'date', 'date-time': 'timestamp_with_timezone', 'time': 'time_without_timezone'}.get(prop.get('format', ''), 'string')
            else:
                key = t or 'string'
        return TYPE_MAP.get(key, key)

    @staticmethod
    def _is_nullable(prop: dict[str, Any]) -> bool:
        t = prop.get('type')
        return isinstance(t, list) and 'null' in t


    def get_table_metadata(self, schema_name: str, table_name: str) -> dict[str, Any]:
        """Always empty — Airbyte is schema-only with no stats catalog, so there are no row counts or column stats to report. Added as a stub for future use. """
        return {'row_count': None, 'column_stats': {}}