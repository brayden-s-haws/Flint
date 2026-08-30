""" Constructs prompt and LLM config needed to generate a description for a table for a given source. Outputs a description of the table that details what the table contains and how it could be used
for business use cases. """
from __future__ import annotations

from apps.catalog.models import Table

TABLE_DESCRIPTION_SYSTEM_MESSAGE: str = (
    "You are an expert in database architecture, SaaS application data, and data warehousing. "
    "Your job is to produce clear, concise descriptions of database tables for a technical business audience. "
    "Write in clear, direct prose for a technical business audience. Do not reference specific personas or job titles. "
    "Use markdown formatting including bold text to make descriptions scannable and useful."
)
OPENAI_TABLE_DESCRIPTION_MODEL: str = "gpt-5.4-mini"
ANTHROPIC_TABLE_DESCRIPTION_MODEL: str = "claude-haiku-4-5"
TABLE_DESCRIPTION_MAX_TOKENS: int = 600


def build_table_description_prompt(table: Table) -> str:
    """
    LLM reviews the provided table details and generates a description for that table based on the provided data.
    """
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
    table_details += """
    Based on the above, write a description of this table using markdown formatting.
    Write 4-6 sentences of prose across 2 short paragraphs.
    First paragraph: describe what the table stores and its role in the broader data model.
    Second paragraph: describe how this data could be used — for analysis, product features, \
operational workflows, or business intelligence. Be specific to the table's content.
    Use bold to highlight key column names or concepts where useful.
    Do not include a title or heading. Do not mention row counts or reference specific personas.

    Example:
    Stores individual **payment** records tied to customer rentals, capturing amount, date, and \
staff association. Acts as the core financial ledger for the rental operation.

    Useful for revenue analysis, period-over-period financial reporting, and identifying \
high-value customers. Can support features like payment history views, refund tracking, \
and automated billing reconciliation.

    Example:
    Captures the many-to-many relationship between **actors** and the **films** they appear in, \
with each row representing a single casting association. Central to understanding the composition \
of the film catalog.

    Enables cast-level reporting, talent attribution across titles, and content discovery features \
based on actor or ensemble patterns. Useful for building recommendation logic or analyzing \
casting trends over time.
    """
    return table_details