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
                            # TODO(review): [Bug 1] Two steps needed here:
                            #
                            #               Step A — Move the PK query ABOVE the column fetch so pk_set
                            #               is available when you build the column dicts:
                            #
                            #                   cursor.execute("SELECT kcu.column_name ...")  # PK query
                            #                   pk_set = {row['column_name'] for row in cursor.fetchall()}
                            #                   cursor.execute("SELECT column_name, data_type, is_nullable ...")
                            #                   raw_columns = cursor.fetchall()
                            #
                            #               Step B — Replace the no-op comprehension with one that transforms
                            #               raw rows into the required catalog shape (rename keys, convert types):
                            #
                            #                   columns = [
                            #                       {
                            #                           'name': col['column_name'],
                            #                           'data_type': col['data_type'],
                            #                           'nullable': col['is_nullable'] == 'YES',
                            #                           'primary_key': col['column_name'] in pk_set,
                            #                       }
                            #                       for col in raw_columns
                            #                   ]
                            columns = [col for col in columns]
                            table['columns'] = columns
                            cursor.execute(f"SELECT column_name FROM information_schema.table_constraints tc JOIN information_schema.key_column_usage kcu ON tc.constraint_name = kcu.constraint_name AND tc.table_schema = kcu.table_schema WHERE constraint_type = 'PRIMARY KEY' AND tc.table_schema = %s AND tc.table_name = %s",
                                           (schema_name, table['table_name']))
                            pk_set = {row['column_name'] for row in cursor.fetchall()}
            # TODO(review): [Bug 4] Delete this entire second loop and move catalog assembly
            #               inside the first loop above. `tables` here only contains tables from
            #               the last schema — every schema in this loop gets the same wrong data.
            #               Also: `'primary_key': table['primary_key']` on line 101 will raise
            #               KeyError — that key was removed. Delete that entry from table_dict.
            #               Target structure (goes inside the first `for schema_name` loop):
            #
            #                   catalog = []          # before the loop
            #                   for schema_name in schema_names:
            #                       ... fetch tables ...
            #                       table_dicts = []
            #                       for table in tables:
            #                           ... build pk_set, then columns list ...
            #                           table_dicts.append({
            #                               'name': table['table_name'],
            #                               'table_type': table['table_type'],
            #                               'columns': columns,   # the transformed list from Bug 1
            #                           })
            #                       catalog.append({'name': schema_name, 'tables': table_dicts})
            #                   return catalog        # after the loop, still inside the with blocks
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