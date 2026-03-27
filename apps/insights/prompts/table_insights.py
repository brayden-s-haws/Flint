from __future__ import annotations

from apps.catalog.models import Table

TABLE_DESCRIPTION_SYSTEM_MESSAGE = ("You are an expert data analyst with a background in standard databases, SaaS application data, data warehouses, and database design. Your job is to analyze table data and provide "
            "analysis on  what tables are likely to contain and how they might be used by a data analyst.")
OPENAI_TABLE_DESCRIPTION_MODEL = "gpt-5.4-mini"
ANTHROPIC_TABLE_DESCRIPTION_MODEL = "claude-haiku-4-5"
TABLE_DESCRIPTION_MAX_TOKENS = 400


def build_table_description_prompt(table: Table) -> str:
    table_details = f"""
    Table: {table.name}
    Schema: {table.schema.name}
    Data Source: {table.schema.source.name}
    Table Type: {table.table_type}
    Row Count: {table.row_count or "Unknown"}
    Columns:
    """
    for column in table.column_set.all():
        table_details += f" - {column.name} ({column.data_type}, {'primary key' if column.primary_key else ''}, {'not nullable' if not column.nullable else ''})\n"
    table_details += f"""
    Based on the above, write a concise 2-3 sentence description of what this table
    likely contains and how it might be used by a data analyst. Do not include an explict row count in your description.
    """
    return table_details