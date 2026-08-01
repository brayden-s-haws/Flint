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
    # TODO(stub): one generic adapter serves ALL Airbyte connectors, parameterized by connector_name.
    #   Optional: short class docstring pointing at devdocs/featuredocs/airbyte-adapter.md.

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
        ...
        # TODO(stub): the core Airbyte -> Flint translation. Structure it like DemoConnector.discover_catalog,
        #   wrapped in try/except that logs and returns [] on failure (mirror PostgreSQLConnector).
        #   1. build the source; read its `discovered_catalog`.
        #   2. iterate `discovered_catalog.streams`. SPIKE FINDING: each item IS an AirbyteStream directly
        #      (no `.stream` wrapper); it exposes `.name`, `.json_schema`, `.source_defined_primary_key`.
        #   3. per stream:
        #        - flatten `source_defined_primary_key` (a LIST OF LISTS, e.g. [['id']]) into a set of PK column names.
        #        - read `json_schema.get('properties', {})`; build one column dict per property with the SAME keys
        #          the sync task expects: {'name', 'data_type', 'nullable', 'primary_key'}
        #          (data_type + nullable come from the two helpers below; primary_key = name in the PK set).
        #        - append {'name': stream.name, 'table_type': 'BASE TABLE', 'columns': [...]}.
        #   4. return a SINGLE synthesized schema: [{'name': <schema_name>, 'tables': [...]}].
        #      OPEN DECISION: what to name the synthesized schema — self.connector_name as-is ('source-stripe'),
        #      or stripped of the 'source-' prefix ('stripe'). Pick one and be consistent.

    # TODO(stub): resolve_data_type(prop: dict[str, Any]) -> str  (module function or static/helper method)
    #   Mirror the CDK's own resolution order (see airbyte_cdk/sql/types.py::_get_airbyte_type):
    #   1. if prop.get('airbyte_type') is set, use it directly (faker's timestamps take this path).
    #   2. else take prop.get('type') — may be a plain str OR a nullable union list like ['null','string'];
    #      pick the single non-'null' element (default 'string' if only ['null'] or type is missing).
    #   3. if that type is 'string', let prop.get('format') refine it:
    #        'date' -> 'date', 'date-time' -> 'timestamp_with_timezone', 'time' -> 'time_without_timezone'.
    #      (Stripe never hits this — its dates are epoch integers — but many connectors emit typed date strings.)
    #   4. look the resulting key up in TYPE_MAP, passing unknown keys straight through as the fallback.

    # TODO(stub): is_nullable(prop: dict[str, Any]) -> bool
    #   - True when prop.get('type') is a list containing 'null'; False for a bare string type.

    def get_table_metadata(self, schema_name: str, table_name: str) -> dict[str, Any]:
        ...
        # TODO(stub): metadata-only by design (Flint inspects metadata, never reads records). No API call needed.
        #   Return exactly {'row_count': None, 'column_stats': {}} like DemoConnector.get_table_metadata.
        #   `table_name` is the Airbyte stream name; `schema_name` is the synthesized schema. Keep the signature.