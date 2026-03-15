from __future__ import annotations

import logging
from typing import Any

import psycopg2
from psycopg2.extras import RealDictCursor

from .base import BaseConnector

logger = logging.getLogger(__name__)


class PostgreSQLConnector(BaseConnector):

    def test_connection(self) -> bool:
        try:
            conn = psycopg2.connect(**self.credentials)
            conn.close()
            return True
        except psycopg2.OperationalError as e:
            logger.error(f"Operational error connecting to PostgreSQL: {e}")
            return False
        except Exception as e:
            logger.error(f"Error connecting to PostgreSQL: {e}")
            return False

    def discover_catalog(self) -> list[dict[str, Any]]:
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

        except Exception as e:
            logger.error(f"Error connecting to PostgreSQL: {e}")
            return []

    def get_table_metadata(self, schema_name: str, table_name: str) -> dict[str, Any]:
        try:
            with psycopg2.connect(**self.credentials) as conn:
                with conn.cursor(cursor_factory=RealDictCursor) as cursor:
                    cursor.execute("SELECT reltuples::bigint AS row_count FROM pg_class JOIN pg_namespace ON pg_class.relnamespace = pg_namespace.oid WHERE nspname = %s AND relname = %s", (schema_name, table_name))
                    row = cursor.fetchone()
                    if row is None:
                        return {'row_count': None}
                    return {'row_count': row['row_count']}
        except Exception as e:
            logger.error(f"Count not query row counts: {e}")
            return { 'row_count': None}