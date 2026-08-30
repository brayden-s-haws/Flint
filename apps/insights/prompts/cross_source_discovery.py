""" Constructs prompts and LLM config needed to run the three-stage cross-source insights pipeline: relationship discovery > hypothesis generation > cross-source insights. Outputs use cases with
business case and starter SQL query. Different stages of the pipeline rely on different tiers of models. The first two stages rely on a fast, inexpensive model, while the final stage relies on a
more expensive model to ensure the final output is high-quality. """
from __future__ import annotations

import json

from django.contrib.contenttypes.models import ContentType

from apps.sources.models import Source
from apps.insights.models import InsightTarget


def _build_ddl_summary(source: Source) -> str:
    """
    Reconstructs pseudo-DDL for a source, needed because we do not have the actual DDL for sources, so it must be inferred. DDL is used as context in all stages of the pipeline to ensure the LLM
    provides valid recommendations and SQL.
    """
    ddl: list[str] = []
    for schema in source.schema_set.all():
        for table in schema.table_set.prefetch_related('column_set').all():
            col_defs = ",\n  ".join(
                f"{col.name} {col.data_type}" for col in table.column_set.all()
            )
            ddl.append(f"CREATE TABLE {table.name} ({col_defs});")
    return "\n\n".join(ddl)

def _get_source_overview_text(source: Source) -> str | None:
    """
    - Retrieves the overview text for a source that will be included as context in the LLM's relationship discovery process.
    - Returns None if a given source does not have an overview insight, or if that overview insight's status is not active.
    """
    content_type = ContentType.objects.get_for_model(Source)
    target = InsightTarget.objects.filter(
        content_type=content_type,
        object_id=source.pk,
        account=source.account,
        insight__insight_type='source_overview',
    ).select_related('insight').first()
    overview_insight = target.insight if target else None
    source_overview = overview_insight.text if overview_insight and overview_insight.status == 'active' else None
    return source_overview


# ---------------------------------------------------------------------------
# Relationship Discovery
# ---------------------------------------------------------------------------

RELATIONSHIP_DISCOVERY_SYSTEM_MESSAGE: str = (
    "You are a senior data architect. Given the schemas of two separate data sources, "
    "you identify how they could be combined for analysis. Your job is purely structural: "
    "find concrete join opportunities — specific source_a table.column to source_b table.column "
    "pairs that share a real-world key (emails, user/customer/account IDs, foreign keys) — and "
    "semantic overlaps, where the two sources describe the same business concept through "
    "different fields. Only propose joins that reference table and column names that actually "
    "appear in the provided schemas; never invent columns. When a key match is approximate "
    "(e.g. email vs. user_email, or a date-range overlap) classify it as fuzzy or temporal "
    "rather than direct. Return only valid JSON — no prose, no markdown, no explanation outside "
    "the JSON structure."
)
OPENAI_RELATIONSHIP_DISCOVERY_MODEL: str = "gpt-5.4-mini"
ANTHROPIC_RELATIONSHIP_DISCOVERY_MODEL: str = "claude-haiku-4-5"
RELATIONSHIP_DISCOVERY_MAX_TOKENS: int = 4000


def build_relationship_discovery_prompt(source_a: Source, source_b: Source, join_key_candidates: list[dict] | None = None) -> str:
    """
    - The LLM reviews the provided sources and identifies potential joins between them. Relies on having the derived DDL and previously generated overviews.
    - The LLM returns details on why it makes sense to join the sources and a confidence score for each join.
    - The score is used downstream to select which relationships to explore further.
    - Relies on the LLM returning only valid JSON and nothing else.
    - Note: does not follow standard formatting conventions (no indentation) to avoid adding unnecessary whitespace when text is sent to the LLM.
    """
    source_a_ddl = _build_ddl_summary(source_a)
    source_b_ddl = _build_ddl_summary(source_b)
    source_a_overview = _get_source_overview_text(source_a)
    source_b_overview = _get_source_overview_text(source_b)

    # join_key_candidates is reserved for Phase 2 pair-scoring hints; unused in Phase 1.

    prompt = f"""You are comparing two separate data sources to find how they can be combined for cross-source analysis.

Source A: "{source_a.name}" (type: {source_a.source_type})

Schema:

{source_a_ddl}
"""

    if source_a_overview:
        prompt += f"""
Overview of Source A:

{source_a_overview}
"""

    prompt += f"""
Source B: "{source_b.name}" (type: {source_b.source_type})

Schema:

{source_b_ddl}
"""

    if source_b_overview:
        prompt += f"""
Overview of Source B:

{source_b_overview}
"""

    prompt += """
Identify how Source A and Source B can be combined. Find:
- Join opportunities: specific Source A table.column to Source B table.column pairs that share a real-world key (emails, user/customer/account IDs, foreign keys).
- Semantic overlaps: where both sources describe the same business concept through different fields, even if there is no direct join key.

Only reference table and column names that actually appear in the schemas above; never invent names. When a key match is approximate (e.g. email vs. user_email, or a shared date range) classify it as fuzzy or temporal rather than direct.

Return ONLY a JSON object in this exact format, with no text before or after it:

{
  "join_opportunities": [
    {
      "source_a_table": "table name in Source A",
      "source_a_column": "column name in Source A",
      "source_b_table": "table name in Source B",
      "source_b_column": "column name in Source B",
      "confidence": "high | medium | low",
      "join_type": "direct | fuzzy | temporal",
      "reasoning": "Why these columns join and what the match is based on."
    }
  ],
  "semantic_overlaps": [
    {
      "concept": "Shared business concept",
      "source_a_signal": "Field or table in Source A that represents it",
      "source_b_signal": "Field or table in Source B that represents it",
      "reasoning": "Why these represent the same concept."
    }
  ]
}
"""
    return prompt


# ---------------------------------------------------------------------------
# Hypothesis Generation
# ---------------------------------------------------------------------------

HYPOTHESIS_SYSTEM_MESSAGE: str = (
    "You are a senior data analyst. Given a confirmed relationship between two data sources — "
    "either a concrete join key or a semantic overlap — you generate specific, actionable "
    "analytical hypotheses that a business analyst could investigate by combining the two "
    "sources. Each hypothesis must be concrete: name the actual metric to compute, the pattern "
    "you would expect to find, and the business decision it would inform. Avoid vague suggestions "
    "like 'gain insights' or 'better understand the data' — every hypothesis should point at a "
    "real question with a real answer. Only reference tables and columns that appear in the "
    "provided schemas; never invent column names — every column you cite must exist in one of the "
    "schemas. Rate your own confidence in each hypothesis's specificity honestly, so weak ones can "
    "be filtered out. Return only valid JSON — no prose, no markdown, no explanation outside the "
    "JSON structure."
)
OPENAI_HYPOTHESIS_MODEL: str = "gpt-5.4-mini"
ANTHROPIC_HYPOTHESIS_MODEL: str = "claude-haiku-4-5"
HYPOTHESIS_MAX_TOKENS: int = 4000


def build_hypothesis_prompt(relationship: dict, source_a: Source, source_b: Source) -> str:
    """
    - The LLM reviews sources that have previously been confirmed to have a joinable relationship in the previous step of the pipeline.
    - Returns a set of hypotheses on various ways the sources could be combined with a business case and specificity score for each hypothesis. The specificity score is used downstream in the pipeline to filter out weak hypotheses.
    - Relies on the LLM returning only valid JSON and nothing else.
    - Note: does not follow standard formatting conventions (no indentation) to avoid adding unnecessary whitespace when text is sent to the LLM.
    """
    relationship_json = json.dumps(relationship, indent=2)
    source_a_ddl = _build_ddl_summary(source_a)
    source_b_ddl = _build_ddl_summary(source_b)

    prompt = f"""Two data sources can be combined based on the following relationship discovered between them:

{relationship_json}

Here are the full schemas of both sources. Ground every hypothesis in tables and columns that actually exist below.

Source A: "{source_a.name}" (type: {source_a.source_type})

{source_a_ddl}

Source B: "{source_b.name}" (type: {source_b.source_type})

{source_b_ddl}

Given the relationship above, generate 3-5 specific, actionable analytical hypotheses that a business analyst could investigate by combining the two sources. For each hypothesis:
- Name the concrete metric or comparison to compute.
- Describe the pattern you would expect to find in the data.
- State the business decision the finding would inform.

Only reference tables and columns that appear in the schemas above; never invent column names. Every column in required_data, and every column used in join_strategy, must exist in one of the schemas.
"""

    prompt += """
Return ONLY a JSON object in this exact format, with no text before or after it:

{
  "hypotheses": [
    {
      "title": "Short plain-English name for the hypothesis",
      "description": "2-3 sentences naming the metric to compute and the pattern to look for.",
      "business_value": "The business decision this finding supports.",
      "join_strategy": "How to combine the two sources to test this — which tables and columns to join.",
      "required_data": ["table.column", "table.column"],
      "specificity_score": 0.0
    }
  ]
}
"""
    return prompt


# ---------------------------------------------------------------------------
# Cross-Source Insight
# ---------------------------------------------------------------------------

CROSS_SOURCE_USE_CASE_SYSTEM_MESSAGE: str = (
    "You are a senior data analyst writing an insight that a business user will read and act on. "
    "Given an analytical hypothesis about combining two data sources, you write a clear, concrete "
    "narrative that explains what the combination reveals, how to measure it (which tables and "
    "columns to join and what to compute), and the business decision it supports. Write for a "
    "smart non-technical reader: specific and jargon-free, no filler. Include a genuine, runnable "
    "starter SQL query that uses real table and column names from the provided schemas — never "
    "invent a table or column that is not in the schemas — a useful starting point, not a toy "
    "example, and intentionally left without WHERE filters or date ranges so the reader can adapt "
    "it. Make sure the SQL is valid, executable standard SQL — for example, never place a window "
    "function such as NTILE inside GROUP BY; compute it in an outer query or subquery instead. If "
    "the two sources cannot be joined directly, provide two separate queries instead. Return only "
    "valid JSON — no prose, no markdown, no explanation outside the JSON structure."
)
OPENAI_CROSS_SOURCE_USE_CASE_MODEL: str = "gpt-5.4"
ANTHROPIC_CROSS_SOURCE_USE_CASE_MODEL: str = "claude-sonnet-4-6"
CROSS_SOURCE_USE_CASE_MAX_TOKENS: int = 4000

def build_cross_source_use_case_prompt(hypothesis: dict, source_a: Source, source_b: Source) -> str:
    """
    - The LLM generates insights for how to use two different sources in unique ways based on the strength of previously generated hypotheses.
    - Is required to generate a valid SQL query based on the provided DDL. If sources cannot be joined directly, provides two separate queries instead.
    - Relies on the LLM returning only valid JSON and nothing else.
    - Note: does not follow standard formatting conventions (no indentation) to avoid adding unnecessary whitespace when text is sent to the LLM.
    """
    hypothesis_json = json.dumps(hypothesis, indent=2)
    source_a_ddl = _build_ddl_summary(source_a)
    source_b_ddl = _build_ddl_summary(source_b)

    prompt = f"""Write a cross-source insight for a business user, based on the following analytical hypothesis about combining two data sources:

{hypothesis_json}

Here are the full schemas of both sources. Every table and column you reference — especially in the SQL — must come from these schemas.

Source A: "{source_a.name}" (type: {source_a.source_type})

{source_a_ddl}

Source B: "{source_b.name}" (type: {source_b.source_type})

{source_b_ddl}

Turn this into a clear, concrete insight that:
- Explains what combining the two sources reveals.
- Describes how to measure it — which tables and columns to join and what to compute.
- States the business decision the insight supports.

Then write a genuine, runnable starter SQL query using real table and column names from the schemas above. Make it a useful starting point — no WHERE filters or date ranges — so the reader can adapt it. If the two sources cannot be joined directly, provide two separate queries instead.
"""

    prompt += """
Return ONLY a JSON object in this exact format, with no text before or after it:

{
  "title": "Short plain-English name for the insight",
  "description": "2-3 sentences explaining what the data combination reveals and how to measure it.",
  "business_value": "The business decision this insight supports.",
  "starter_sql": "SELECT ... FROM ... JOIN ... ;"
}
"""
    return prompt