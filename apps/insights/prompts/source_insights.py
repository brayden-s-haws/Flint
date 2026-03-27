from __future__ import annotations

from apps.sources.models import Source

# TODO(stub): Add a SOURCE_OVERVIEW_SYSTEM_MESSAGE constant (str) — describe the AI's role.
#   It should position the model as an expert data analyst who can infer what a data source
#   contains and how analysts would use it, based on source metadata and table names.

# TODO(stub): Add an ANTHROPIC_SOURCE_OVERVIEW_MODEL constant — use 'claude-haiku-4-5'

# TODO(stub): Add a SOURCE_OVERVIEW_MAX_TOKENS constant — 400 is a reasonable starting point


# TODO(stub): Define build_source_overview_prompt(source: Source) -> str
#   This function builds the prompt string passed to the LLM. Include:
#   1. Source name (source.name)
#   2. Source type (source.source_type)
#   3. All table names across all schemas — iterate source.schema_set.all(), then
#      for each schema iterate schema.table_set.all() to collect table names.
#      Flatten into a single list and format as a bullet list or comma-separated string.
#   4. A closing instruction asking the model to describe what this source likely contains
#      and how an analyst might use it — 2-3 sentences, no markdown formatting.