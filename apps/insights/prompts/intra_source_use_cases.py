from __future__ import annotations

from django.contrib.contenttypes.models import ContentType

from apps.sources.models import Source
from apps.insights.models import InsightTarget


USE_CASE_SYSTEM_MESSAGE: str = (
    "You are a senior data analyst. Given a database schema and context about a data source, "
    "you generate concrete, actionable analytical use cases that can be derived from the tables. "
    "Each use case must include a genuine, runnable SQL query using the actual table and column names provided. "
    "Return only valid JSON — no prose, no markdown, no explanation outside the JSON structure."
)

OPENAI_USE_CASE_MODEL: str = "gpt-5.4-mini"
ANTHROPIC_USE_CASE_MODEL: str = "claude-haiku-4-5"
USE_CASE_MAX_TOKENS: int = 4000


def build_use_case_suggestions_prompt(source: Source) -> str:
    # Build DDL-style summary from catalog
    ddl_lines: list[str] = []
    for schema in source.schema_set.all():
        for table in schema.table_set.prefetch_related('column_set').all():
            col_defs = ",\n  ".join(
                f"{col.name} {col.data_type}" for col in table.column_set.all()
            )
            ddl_lines.append(f"CREATE TABLE {table.name} (\n  {col_defs}\n);")
    ddl_summary = "\n\n".join(ddl_lines)

    # Fetch existing source overview insight text if available
    content_type = ContentType.objects.get_for_model(Source)
    target = InsightTarget.objects.filter(
        content_type=content_type,
        object_id=source.pk,
        account=source.account,
        insight__insight_type='source_overview',
    ).select_related('insight').first()
    overview_insight = target.insight if target else None
    source_overview = overview_insight.text if overview_insight and overview_insight.status == 'active' else None

    prompt = f"""You are analyzing a data source named "{source.name}" (type: {source.source_type}).

Here is the database schema:

{ddl_summary}
"""

    if source_overview:
        prompt += f"""
Here is a high-level description of this data source:

{source_overview}
"""

    prompt += """
Generate 4-6 distinct, concrete analytical use cases that can be derived by joining two or more tables in this source. Each use case must:
- Reference real table and column names from the schema above
- Include a genuine, runnable SELECT query (not a toy example)
- Be immediately actionable — no WHERE filters or date ranges needed to make it useful

Return ONLY a JSON object in this exact format, with no text before or after it:

{
  "use_cases": [
    {
      "title": "Short plain-English name for the use case",
      "description": "2-3 sentences explaining what insight this surfaces and why it is useful.",
      "tables": ["TableA", "TableB"],
      "starter_sql": "SELECT ... FROM ... JOIN ... GROUP BY ... ORDER BY ...;"
    }
  ]
}
"""
    return prompt