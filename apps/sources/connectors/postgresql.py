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
            with psycopg2.connect(**self.credentials) as conn:
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
                    # TODO(review): [Bug 4] The catalog must be built INSIDE this loop, not in a
                    #               second separate loop below. Each iteration fetches `tables` for
                    #               one schema — after the loop exits, `tables` only holds the last
                    #               schema's results. Restructure like this:
                    #
                    #                   catalog = []                        # ← before the loop
                    #                   for schema_name in schema_names:
                    #                       ... fetch tables ...
                    #                       table_dicts = []
                    #                       for table in tables:
                    #                           ... fetch columns, pk_set ...
                    #                           table_dicts.append({...})
                    #                       catalog.append({'name': schema_name, 'tables': table_dicts})
                    #                   return catalog                      # ← after the loop
                    #
                    #               Then delete the entire second loop (lines 48–59 below).
                    for schema_name in schema_names:
                        cursor.execute("SELECT table_name, table_type FROM information_schema.tables WHERE table_schema = %s", (schema_name,))
                        tables = cursor.fetchall()
                        tables = [table for table in tables]
                        for table in tables:
                            cursor.execute(f"SELECT column_name, data_type, is_nullable FROM information_schema.columns WHERE table_schema = %s AND table_name = %s", (schema_name, table['table_name']))
                            columns = cursor.fetchall()
                            # TODO(review): [Bug 1] This copies rows as-is. Each `col` still has
                            #               psycopg2 key names ('column_name', 'is_nullable': 'YES'/'NO')
                            #               instead of the catalog schema keys ('name', 'nullable': bool).
                            #               Replace this line with a list comprehension that transforms
                            #               each row into the required dict shape:
                            #
                            #                   [
                            #                       {
                            #                           'name': col['column_name'],
                            #                           'data_type': col['data_type'],
                            #                           'nullable': col['is_nullable'] == 'YES',
                            #                           'primary_key': col['column_name'] in pk_set,
                            #                       }
                            #                       for col in raw_columns
                            #                   ]
                            #
                            #               Note: `pk_set` must be built first (fix Bug 2 below),
                            #               then used here in the same comprehension.
                            columns = [col for col in columns]
                            table['columns'] = columns
                            # TODO(review): [Bug 2] `constraint_type` is NOT a column on
                            #               `information_schema.key_column_usage` — it lives on
                            #               `information_schema.table_constraints`. This query will
                            #               raise a database error at runtime.
                            #
                            #               Replace with a JOIN between the two tables:
                            #
                            #                   SELECT kcu.column_name
                            #                   FROM information_schema.table_constraints tc
                            #                   JOIN information_schema.key_column_usage kcu
                            #                     ON tc.constraint_name = kcu.constraint_name
                            #                    AND tc.table_schema    = kcu.table_schema
                            #                   WHERE tc.constraint_type = 'PRIMARY KEY'
                            #                     AND tc.table_schema = %s
                            #                     AND tc.table_name   = %s
                            #
                            #               Bind (schema_name, table['table_name']) as parameters.
                            #               Then collect into a set:
                            #                   pk_set = {row['column_name'] for row in cursor.fetchall()}
                            #               Use pk_set in the column comprehension above (Bug 1).
                            cursor.execute(f"SELECT column_name FROM information_schema.key_column_usage WHERE constraint_type = 'PRIMARY KEY' AND table_schema = %s AND table_name = %s", (schema_name, table['table_name']))
                            primary_keys = cursor.fetchall()
                            primary_keys = [pk['column_name'] for pk in primary_keys]
                            # TODO(review): [Bug 3] `primary_key` belongs on each COLUMN dict as a bool,
                            #               not on the table dict as a scalar. Remove this line entirely.
                            #               Once Bug 1 and Bug 2 are fixed, each column dict will already
                            #               have 'primary_key': col['column_name'] in pk_set — a bool.
                            #               The table dict itself should only have 'name', 'table_type',
                            #               and 'columns'.
                            table['primary_key'] = primary_keys[0] if primary_keys else None
            # TODO(review): [Bug 4 continued] Delete this entire second loop. It re-iterates
            #               schema_names but `tables` at this point only contains the tables
            #               from the last schema in the first loop. Every schema would get the
            #               same wrong tables. Move catalog assembly inside the first loop above.
            catalog = []
            for schema_name in schema_names:
                schema_dict = {'name': schema_name, 'tables': []}
                for table in tables:
                    table_dict = {
                        'name': table['table_name'],
                        'table_type': table['table_type'],
                        'columns': table['columns'],
                        'primary_key': table['primary_key']
                    }
                    schema_dict['tables'].append(table_dict)
                catalog.append(schema_dict)
            return catalog
        except Exception as e:
            logger.error(f"Error connecting to PostgreSQL: {e}")
            return []