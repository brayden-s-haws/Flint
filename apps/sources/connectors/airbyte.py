from __future__ import annotations

import logging
from typing import Any
import airbyte as ab

from .base import BaseConnector

logger = logging.getLogger(__name__)


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

    def __init__(self, credentials: dict[str, Any], connector_name: str) -> None:
        super().__init__(credentials)
        self.connector_name = connector_name

    def _get_source(self) -> Any:
        return ab.get_source(self.connector_name, config=self.credentials, install_if_missing=True)

    def test_connection(self) -> bool:
        try:
            self._get_source().check()
            return True
        except Exception as e:
            logger.error(f"AirbyteConnector test_connection failed: {e}")
            return False

    def discover_catalog(self) -> list[dict[str, Any]]:
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
        return {'row_count': None, 'column_stats': {}}