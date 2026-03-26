# insights app - MVP Checklist

## Models

- [x] `Insight` — LLM-generated or manual insight content (text, type, status)
- [x] `InsightTarget` — links an insight to a specific table (polymorphic linking deferred, just table FK for MVP)
- [x] `InsightPrompt` — versioned LLM prompt templates stored in database

## Admin

- [x] Register `Insight`, `InsightTarget`, `InsightPrompt` in admin

## Prompts

Prompts live in `apps/insights/prompts/` — one file per use case. Services import from here rather than defining prompts inline.

- [x] `prompts/__init__.py` — empty, makes it a package
- [x] `prompts/table_insights.py` — `build_table_description_prompt(table: Table) -> str` function that builds the prompt string from a Table object (name, schema, source, columns)

## Services

- [x] LLM provider abstraction — base interface for generating insights (`services/base.py`)
- [x] OpenAI provider — call OpenAI API to generate table descriptions (`services/openai_service.py`)
- [x] Anthropic provider — call Anthropic API to generate table descriptions (`services/anthropic_service.py`)
- [x] Provider config — `InsightPrompt.provider` field selects provider per prompt; `services/provider.py` returns the correct service instance

## Views

- [x] Generate insight action — trigger LLM description generation for a single table (sync call)
- [x] Insight detail view — view a generated insight
- [x] Insight list view — browse all insights for the account

## Templates

- [x] `insights/insight_list.html` — list of generated insights
- [x] `insights/insight_detail.html` — full insight view
- [x] Inline insight display on `catalog/table_detail.html` (generate button + result)

## URLs

- [x] `/insights/` — list
- [x] `/insights/<id>/` — detail
- [x] `/insights/generate/<table_id>/` — trigger generation for a table

## Prompt Architecture

There are two types of LLM use cases in this app:

**Hardcoded prompts** (e.g. table descriptions) — prompt lives as a Python file in `apps/insights/prompts/`. The prompt text, model, max tokens, and system message are all defined in code. Users cannot edit these. Services import from the prompts file directly. Provider is the only user choice.

**User-defined prompts** (future) — prompt text is written by the user and stored in the `InsightPrompt` database model. These are versioned, named, and associated with an account. The `InsightPrompt.provider` field controls which LLM is used. Services receive an `InsightPrompt` object and use its `.prompt` field.

The `InsightPrompt` model and `get_service()` in `provider.py` are designed for user-defined prompt flows. Do not use them for hardcoded prompt flows.

### Fix needed: table description generate flow

Currently `GenerateInsightView` looks up an `InsightPrompt` from the database to determine the provider. This is wrong for the table description use case — the prompt is hardcoded in `table_insights.py` and the only user input is provider choice.

Steps to fix:

1. **Update `get_service()` in `services/provider.py`** — change the parameter from `insight_prompt: InsightPrompt` to `provider: str`. The if/elif already only uses `insight_prompt.provider`, so swap that to the plain string.

2. **Update `GenerateInsightView.post()` in `views.py`** — remove the `InsightPrompt` DB lookup. Read `provider = request.POST.get('provider', 'openai')` from the form instead. Call `get_service(provider)` directly. Pass `insight_prompt=None` when creating the `Insight`.

3. **Update the generate form in `catalog/table_detail.html`** — add a `<select name="provider">` with `openai` and `anthropic` options inside the existing form.

- [ ] Fix `get_service()` to accept `str` instead of `InsightPrompt`
- [ ] Fix `GenerateInsightView` to read provider from POST, bypass DB lookup
- [ ] Add provider selector to the generate form in `catalog/table_detail.html`

## MVP Notes
Note to self: use branch review skill before merging to main. And then create a new branch for the next item

- Sync LLM calls only (no Celery, no background tasks)
- One table at a time (no batch generation)
- InsightBuilder and cross-source insights are deferred