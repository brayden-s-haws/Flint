from __future__ import annotations

import logging
from typing import Any
import airbyte as ab

from .base import BaseConnector

logger = logging.getLogger(__name__)


# TODO(stub): TYPE_MAP — module-level dict mapping Airbyte JSON-schema types (and airbyte_type refinements)
#   -> Flint `data_type` strings. Mirror DemoConnector.TYPE_MAP's pattern (a module-level constant).
#   Keys confirmed from the Phase 1 spike against source-stripe + source-faker:
#     'string', 'integer', 'number', 'boolean', 'object', 'array'  (plain json-schema types)
#     plus airbyte_type values such as 'timestamp_with_timezone'   (refinements, only sometimes present)
#   Choose readable, roughly Postgres-flavored output strings (e.g. 'character varying', 'integer',
#   'numeric', 'boolean', 'timestamp with time zone', 'jsonb') so the catalog reads consistently
#   alongside the native PostgreSQL/Demo connectors. Provide a sensible fallback for unknown keys
#   (see resolve_data_type TODO below).

TYPE_MAP = {
    'string': 'character varying',
    'integer': 'integer',
    'number': 'numeric',
    'boolean': 'boolean',
    'object': 'jsonb',
    'array': 'jsonb',
    'timestamp_with_timezone': 'timestamp with time zone',
}


class AirbyteConnector(BaseConnector):
    # TODO(stub): one generic adapter serves ALL Airbyte connectors, parameterized by connector_name.
    #   Optional: short class docstring pointing at devdocs/featuredocs/airbyte-adapter.md.

    # TODO(stub): __init__(self, credentials: dict[str, Any], connector_name: str) -> None
    #   - `credentials`: the decrypted Airbyte config dict (e.g. Stripe -> {'client_secret','account_id','start_date'})
    #   - `connector_name`: the Airbyte connector id to launch, e.g. 'source-stripe'. Do NOT read this from
    #     `credentials` — the feature doc rejected putting it in the config JSON (it is SourceType metadata,
    #     plumbed in from SourceType.airbyte_connector_name in Phase 3, not a per-source secret).
    #   - call super().__init__(credentials) so self.credentials is set, then store self.connector_name.
    #   NOTE: this two-arg signature intentionally diverges from BaseConnector's one-arg convention. Phase 3
    #   updates the registry + the two call sites (tasks.py, views.py::test_connection) to pass the name.
    #   For Phase 2 verification, construct directly: AirbyteConnector(config, "source-stripe").

    # TODO(stub): private helper to BUILD the PyAirbyte source object, reused by test_connection + discover_catalog.
    #   Signature like `_get_source(self) -> Any` (or the airbyte Source type).
    #   Body: return ab.get_source(self.connector_name, config=self.credentials, install_if_missing=True)
    #   - first use installs the connector into an isolated venv (slow, needs network egress) — acceptable
    #     because sync runs in Celery; note this for the Phase 5 worker environment.

    def test_connection(self) -> bool:
        ...
        # TODO(stub): mirror PostgreSQLConnector.test_connection's try/except style.
        #   - build the source via the helper, then call source.check().
        #   - SPIKE FINDING: check() returns None on success and RAISES on failure. So do NOT `return source.check()`.
        #     Instead: try: source.check(); return True   except Exception as e: logger.error(...); return False
        #   - KNOWN Phase-5 caveat (do NOT solve here): source-stripe.check() 401s on the Connect `accounts`
        #     stream for non-Connect accounts, so this will return False for Stripe until Connect is enabled or
        #     this method is made stream-tolerant. Leave tolerant handling to Phase 5; just be aware of it.

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
    #   - prefer prop.get('airbyte_type') when present (Stripe returns None here, faker returned
    #     'timestamp_with_timezone' — testing both is what surfaced this ordering).
    #   - else take prop.get('type'), which may be a plain str OR a nullable union list like ['null','string'];
    #     pick the non-'null' element (default to 'string' if the list is only ['null'] or type is missing).
    #   - look the resulting key up in TYPE_MAP, passing unknown keys straight through as the fallback.

    # TODO(stub): is_nullable(prop: dict[str, Any]) -> bool
    #   - True when prop.get('type') is a list containing 'null'; False for a bare string type.

    def get_table_metadata(self, schema_name: str, table_name: str) -> dict[str, Any]:
        ...
        # TODO(stub): metadata-only by design (Flint inspects metadata, never reads records). No API call needed.
        #   Return exactly {'row_count': None, 'column_stats': {}} like DemoConnector.get_table_metadata.
        #   `table_name` is the Airbyte stream name; `schema_name` is the synthesized schema. Keep the signature.