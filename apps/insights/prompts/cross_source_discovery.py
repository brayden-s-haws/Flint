from __future__ import annotations

# TODO(stub): Imports. You'll likely need:
#   - from django.contrib.contenttypes.models import ContentType
#   - from apps.sources.models import Source
#   - from apps.insights.models import InsightTarget
#   Model your import list on apps/insights/prompts/intra_source_use_cases.py, but
#   only import what each builder actually uses.


# ---------------------------------------------------------------------------
# Step 3 — Relationship Discovery
# ---------------------------------------------------------------------------

# TODO(stub): Module-level constants for the relationship-discovery call. Mirror the
#   naming convention in intra_source_use_cases.py:
#     RELATIONSHIP_DISCOVERY_SYSTEM_MESSAGE: str
#         A strict "you are a data analyst; return ONLY valid JSON, no markdown" system
#         message. The job here is structural: find concrete table.column -> table.column
#         join opportunities and semantic overlaps between TWO sources.
#     OPENAI_RELATIONSHIP_MODEL / ANTHROPIC_RELATIONSHIP_MODEL: str
#         Use the CHEAPER model tier here (this is discovery, not the final user-facing
#         write). See "Cost and Quality Controls" in the featuredoc.
#     RELATIONSHIP_MAX_TOKENS: int


def build_relationship_discovery_prompt(
    source_a: "Source",
    source_b: "Source",
    join_key_candidates: list[dict] | None = None,
) -> str:
    # TODO(stub): Build a DDL-style schema summary for BOTH sources, clearly labelled so
    #   the LLM can tell which table belongs to which source. Reuse the schema/table/
    #   column loop from intra_source_use_cases.py:22-30, but run it twice and prefix each
    #   block, e.g. "Source A: {source_a.name} ({source_a.source_type})" / "Source B: ...".
    #   The labels matter — Step 3's output references which source each table came from.
    #
    # TODO(stub): join_key_candidates is the Step 2 (pair-scoring) output and is UNUSED in
    #   Phase 1 (Step 2 doesn't exist yet). Keep the parameter with a None default so the
    #   signature is stable for Phase 2; if provided later, render them as hints in the
    #   prompt ("These columns look like likely join keys: ..."). For now, do nothing with it.
    #
    # TODO(stub): Optionally include each source's Source Overview insight text as context.
    #   If you do, fetch it the CORRECT way — filter InsightTarget by BOTH the source
    #   (content_type + object_id) AND insight__insight_type='source_overview', as in
    #   views.py:79-83. Do NOT copy the latent bug in intra_source_use_cases.py:33-37, which
    #   omits the insight_type filter and grabs whichever target is first.
    #
    # TODO(stub): Ask for the exact Step 3 JSON shape from the featuredoc:
    #     {
    #       "join_opportunities": [
    #         {"source_a_table", "source_a_column", "source_b_table", "source_b_column",
    #          "confidence": "high|medium|low", "join_type": "direct|fuzzy|temporal",
    #          "reasoning"}
    #       ],
    #       "semantic_overlaps": [
    #         {"concept", "source_a_signal", "source_b_signal", "reasoning"}
    #       ]
    #     }
    #   End with "Return ONLY a JSON object in this exact format, with no text before or
    #   after it." (copy the framing from build_use_case_suggestions_prompt).
    #
    # TODO(stub): Return the assembled prompt string. Return type is str.
    ...


# ---------------------------------------------------------------------------
# Step 4 — Hypothesis Generation
# ---------------------------------------------------------------------------

# TODO(stub): Constants for the hypothesis call:
#     HYPOTHESIS_SYSTEM_MESSAGE: str  — "given a confirmed join, what could a business
#         analyst actually discover?" Focus shifts from structural to analytical value.
#         Still JSON-only.
#     OPENAI_HYPOTHESIS_MODEL / ANTHROPIC_HYPOTHESIS_MODEL: str  — cheaper tier again.
#     HYPOTHESIS_MAX_TOKENS: int


def build_hypothesis_prompt(relationship: dict) -> str:
    # TODO(stub): `relationship` is ONE element from Step 3's output (a single
    #   join_opportunity or semantic_overlap dict). Render its fields into the prompt so
    #   the LLM knows exactly which join to reason over.
    #
    # TODO(stub): Ask: "Given these two sources can be joined on X, what are 3-5 specific,
    #   actionable insights a business analyst could extract? Name the metrics, the expected
    #   patterns, and the business decision each supports." Be explicit that vague output is
    #   unwanted.
    #
    # TODO(stub): Request the Step 4 JSON shape:
    #     {"hypotheses": [
    #        {"title", "description", "business_value", "join_strategy",
    #         "required_data": ["table.column", ...], "specificity_score": 0.0-1.0}
    #     ]}
    #   specificity_score is the LLM's self-assessment — Phase 3's quality filter uses it.
    #
    # TODO(stub): Return the prompt string. Return type is str.
    ...


# ---------------------------------------------------------------------------
# Step 6 — Cross-Source Insight (final user-facing write)
# ---------------------------------------------------------------------------

# TODO(stub): Constants for the insight-writing call:
#     CROSS_SOURCE_INSIGHT_SYSTEM_MESSAGE: str  — this is the output the USER reads, so the
#         system message should ask for a clear, concrete narrative: what the combination
#         reveals, how to measure it, and the business decision it supports.
#     OPENAI_CROSS_SOURCE_INSIGHT_MODEL / ANTHROPIC_CROSS_SOURCE_INSIGHT_MODEL: str  — use
#         the BETTER model tier here (only the final write justifies the cost).
#     CROSS_SOURCE_INSIGHT_MAX_TOKENS: int


def build_cross_source_insight_prompt(hypothesis: dict) -> str:
    # TODO(stub): `hypothesis` is one surviving element from Step 4's output. Render its
    #   fields (title, description, business_value, join_strategy, required_data) into the
    #   prompt as the brief for the final write.
    #
    # TODO(stub): Require a runnable, cross-source starter SQL query that references REAL
    #   table/column names from the hypothesis. It's display-only for now (no execution),
    #   but must be genuine, not a toy. If the two sources can't be directly joined, the
    #   spec allows two separate queries.
    #
    # TODO(stub): Request the Step 6 JSON shape that gets stored in Insight.structured_data:
    #     {"title", "description", "business_value", "starter_sql"}
    #   Keep SQL in its own field — never embed it in prose (matches the use_case pattern).
    #
    # TODO(stub): Return the prompt string. Return type is str.
    ...