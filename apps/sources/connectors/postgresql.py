""" Native PostgreSQL connector. Reads schema structure from information_schema and per-table statistics from the pg_stats/pg_class catalogs — metadata only, never row data. """
from __future__ import annotations

import logging
from typing import Any

import psycopg2
from psycopg2.extras import RealDictCursor

from .base import BaseConnector


logger = logging.getLogger(__name__)


class PostgreSQLConnector(BaseConnector):
    """
    - BaseConnector for PostgreSQL; credentials are the psycopg2 connection kwargs (host, port, dbname, user, password).
    - Each method opens its own short-lived connection and swallows errors into a safe fallback so a bad source never crashes the sync task.
    """

    def test_connection(self) -> bool:
        try:
            conn = psycopg2.connect(**self.credentials)
            conn.close()
            return True
        except psycopg2.OperationalError as exc:
            logger.error("Operational error connecting to PostgreSQL: %s", type(exc).__name__)
            return False
        except Exception as exc:
            logger.error("Error connecting to PostgreSQL: %s", type(exc).__name__)
            return False

    def discover_catalog(self) -> list[dict[str, Any]]:
        """Walk information_schema to build the schema→table→column tree, skipping the system schemas (information_schema, pg_catalog, pg_toast) and flagging primary-key columns."""
        try:
            with psycopg2.connect(**self.credentials) as conn:
                with conn.cursor(cursor_factory=RealDictCursor) as cursor:
                    cursor.execute("SELECT schema_name FROM information_schema.schemata")
                    schemas = cursor.fetchall()
                    schema_names = [schema['schema_name'] for schema in schemas]
                    schema_names = [name for name in schema_names if name not in ('information_schema', 'pg_catalog', 'pg_toast')]
                    catalog = []
                    for schema_name in schema_names:
                        cursor.execute("SELECT table_name, table_type FROM information_schema.tables WHERE table_schema = %s", (schema_name,))
                        tables = cursor.fetchall()
                        table_dicts = []
                        for table in tables:
                            cursor.execute(
                                "SELECT column_name FROM information_schema.table_constraints tc JOIN information_schema.key_column_usage kcu ON tc.constraint_name = kcu.constraint_name AND tc.table_schema = kcu.table_schema WHERE constraint_type = 'PRIMARY KEY' AND tc.table_schema = %s AND tc.table_name = %s",
                                (schema_name, table['table_name']))
                            pk_set = {row['column_name'] for row in cursor.fetchall()}
                            cursor.execute("SELECT column_name, data_type, is_nullable FROM information_schema.columns WHERE table_schema = %s AND table_name = %s", (schema_name, table['table_name']))
                            raw_columns = cursor.fetchall()
                            columns = [
                                {
                                    'name': col['column_name'],
                                    'data_type': col['data_type'],
                                    'nullable': col['is_nullable'] == 'YES',
                                    'primary_key': col['column_name'] in pk_set
                                }
                                for col in raw_columns
                            ]
                            table_dicts.append({'name': table['table_name'], 'table_type': table['table_type'], 'columns': columns})
                        catalog.append({'name': schema_name, 'tables': table_dicts})
                return catalog

        except Exception as exc:
            logger.error("Error connecting to PostgreSQL: %s", type(exc).__name__)
            return []

    def get_table_metadata(self, schema_name: str, table_name: str) -> dict[str, Any]:
        """
        - Return row count and per-column stats from the planner catalogs (pg_class.reltuples, pg_stats) — an estimate, not a COUNT(*), so it's cheap and reads no rows.
        - For each column: null fraction, distinct count (pg_stats reports n_distinct as a negative ratio when proportional to row count, so it's converted back to an absolute count), and most-common values.
        """
        try:
            with psycopg2.connect(**self.credentials) as conn:
                with conn.cursor(cursor_factory=RealDictCursor) as cursor:
                    cursor.execute("SELECT reltuples::bigint AS row_count FROM pg_class JOIN pg_namespace ON pg_class.relnamespace = pg_namespace.oid WHERE nspname = %s AND relname = %s", (schema_name, table_name))
                    row = cursor.fetchone()
                    if row is None:
                        return { 'row_count': None, 'column_stats': {}}
                    cursor.execute("SELECT attname, null_frac, n_distinct, most_common_vals FROM pg_stats WHERE schemaname = %s and tablename = %s", (schema_name, table_name))
                    column_stats = cursor.fetchall()
                    stats = {}
                    for col in column_stats:
                        raw_mcv = col['most_common_vals']
                        common_values = raw_mcv.strip('{}').split(',') if raw_mcv else []
                        n_distinct = col['n_distinct']
                        distinct_count = int(abs(n_distinct) * row['row_count']) if n_distinct < 0 else int(n_distinct)
                        stats[col['attname']] = {
                            'null_fraction': col['null_frac'],
                            'distinct_count': distinct_count,
                            'common_values': common_values
                        }
                    return {'row_count': row['row_count'], 'column_stats': stats}
        except Exception as exc:
            logger.error("Could not query row counts: %s", type(exc).__name__)
            return { 'row_count': None, 'column_stats': {}}