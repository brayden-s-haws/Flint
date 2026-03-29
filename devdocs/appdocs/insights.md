# insights app - MVP Checklist

## Prompt Architecture

There are two types of LLM use cases in this app:

**Hardcoded prompts** — prompt lives as a Python file in `apps/insights/prompts/`, one file per use case. The prompt text, system message, model, and max tokens are all defined in code. Users cannot edit these. Services import from the prompts file directly. The provider (openai vs anthropic) is the only runtime variable.

- Use this pattern when: the prompt is product-defined and should not vary per user (e.g. table descriptions, source overviews)
- Trigger: automatic (lazy on first view, or at end of a sync — see each use case below)
- `InsightPrompt` DB model is NOT used for these flows

**User-defined prompts** (future) — prompt text is written by the user and stored in the `InsightPrompt` database model. Versioned, named, associated with an account. Services receive an `InsightPrompt` object and use its `.prompt` field and `.provider` field.

- Use this pattern when: users should be able to write and iterate on their own prompts
- `InsightPrompt` model and `get_service(provider: str)` are the right tools for these flows

### `get_service()` contract

`services/provider.py` accepts a plain `provider: str` (`'openai'` or `'anthropic'`). Hardcoded flows pass the string directly. User-defined flows pass `insight_prompt.provider`. The function never receives a full model object.

### Provider rules

- **Hardcoded/auto-generated insights** (table descriptions, source overviews, etc.) → always use `'anthropic'`
- **User-defined prompts** → user selects provider via `InsightPrompt.provider` field (openai or anthropic)

---

## Models

- [x] `Insight` — LLM-generated or manual insight content (text, type, status)
- [x] `InsightTarget` — polymorphic link from an insight to any target object (Table, Source, Column, etc.) — see GenericForeignKey section below
- [x] `InsightPrompt` — versioned LLM prompt templates stored in database (for user-defined flows only)

### InsightTarget: GenericForeignKey

`InsightTarget` needs to support linking insights to any model — Tables, Sources, Columns, Schemas, and more in the future. The right Django pattern is `GenericForeignKey` from `django.contrib.contenttypes`.

**How it works:**
- `content_type` FK → stores *which model* the target is (e.g. `catalog.Table`)
- `object_id` → stores the pk of the target object
- `target` → a virtual `GenericForeignKey` field that combines the two; not stored in the DB itself

**Model change** in `apps/insights/models.py`:
```python
from django.contrib.contenttypes.models import ContentType
from django.contrib.contenttypes.fields import GenericForeignKey

class InsightTarget(TenantAwareModel):
    insight = models.ForeignKey(Insight, on_delete=models.CASCADE)
    content_type = models.ForeignKey(ContentType, on_delete=models.CASCADE)
    object_id = models.PositiveIntegerField()
    target = GenericForeignKey('content_type', 'object_id')
```

Note: `django.contrib.contenttypes` is already in `INSTALLED_APPS` by default — no settings change needed.

Run `makemigrations` and `migrate` after updating the model.

**Places that need updating after this change:**

1. **`apps/catalog/views.py` line 30** — `InsightTarget.objects.filter(target=self.object, ...)` won't work with GenericForeignKey. Replace with:
   ```python
   content_type = ContentType.objects.get_for_model(Table)
   insight_targets = InsightTarget.objects.filter(
       content_type=content_type,
       object_id=self.object.pk,
       account=request.account,
   ).select_related('insight')
   ```
   Import `ContentType` from `django.contrib.contenttypes.models` at the top of the file.

2. **`apps/insights/views.py` line 53** — `InsightTarget.objects.create(..., target=table)` won't work. Replace with:
   ```python
   content_type = ContentType.objects.get_for_model(table)
   InsightTarget.objects.create(
       account=request.account,
       insight=insight,
       content_type=content_type,
       object_id=table.pk,
   )
   ```

3. **`apps/insights/insight_detail.html`** — `insight.insighttarget_set.first().target` still works correctly; `GenericForeignKey` resolves the object transparently when accessed on an instance.

- [x] Update `InsightTarget` model to use `GenericForeignKey`
- [x] Run `makemigrations` and `migrate`
- [x] Update `apps/catalog/views.py` — replace `filter(target=...)` with `filter(content_type=..., object_id=...)`
- [x] Update `apps/insights/views.py` — replace `create(..., target=table)` with `create(..., content_type=..., object_id=...)`

## Admin

- [x] Register `Insight`, `InsightTarget`, `InsightPrompt` in admin

## Prompts

Prompts live in `apps/insights/prompts/` — one file per use case. Each file owns: system message, model constant, max tokens constant, and a `build_*_prompt()` function.

- [x] `prompts/__init__.py` — empty, makes it a package
- [x] `prompts/table_insights.py` — `build_table_description_prompt(table: Table) -> str`
- [x] `prompts/source_insights.py` — `build_source_overview_prompt(source: Source) -> str` — context: source name, source type, and list of all table names discovered in the sync

## Services

- [x] LLM provider abstraction — base interface (`services/base.py`)
- [x] OpenAI provider — `services/openai_service.py`
- [x] Anthropic provider — `services/anthropic_service.py`
- [x] Fix `get_service()` in `services/provider.py` — change parameter from `InsightPrompt` object to `provider: str`

## Views

- [x] Insight detail view — `InsightDetailView`
- [x] Insight list view — `InsightListView`
- [x] Remove `GenerateInsightView` and its URL — table descriptions are now auto-generated, not manually triggered

## Templates

- [x] `insights/insight_list.html` — list of generated insights
- [x] `insights/insight_detail.html` — full insight view
- [x] Update `catalog/table_detail.html` — remove the generate form; insight auto-displays when present
- [x] Add source overview insight card to `sources/source_detail.html`

## URLs

- [x] `/insights/` — list
- [x] `/insights/<id>/` — detail
- [x] Remove `/insights/generate/<table_id>/` — no longer needed

---

## Use Case: Table Description

**Prompt file:** `prompts/table_insights.py`
**Trigger:** Lazy — generated automatically on first view of `catalog/table_detail.html` if no insight exists yet
**Provider:** Always `'anthropic'` — hardcoded for all auto-generated insights
**Target:** `InsightTarget` linking `Insight` → `Table`

### Implementation steps

- [x] Fix `get_service()` to accept `provider: str`
- [x] Update `TableDetailView.get_context_data` in `apps/catalog/views.py`:
  - After fetching insights, if list is empty: call `get_service('anthropic')`, call `service.generate_table_description(table)`, create `Insight` + `InsightTarget`, wrap in try/except so a failed LLM call doesn't break the page
  - Import `get_service`, `build_table_description_prompt`, `Insight`, `InsightTarget`
- [x] Update `catalog/table_detail.html` — remove the generate `<form>`, just render insights inline
- [x] Remove `GenerateInsightView` from `apps/insights/views.py` and its URL from `apps/insights/urls.py`

---

## Use Case: Source Overview

**Prompt file:** `prompts/source_insights.py` (to build)
**Trigger:** End of first sync — called from `sync_source` view in `apps/sources/views.py` after tables are saved, only if no source-level insight exists yet
**Provider:** Always `'anthropic'` — hardcoded for all auto-generated insights
**Target:** `InsightTarget` linking `Insight` → `Source` — now that `InsightTarget` uses `GenericForeignKey`, it can target any model including `Source`

**What the prompt should include:**
- Source name and type (e.g. PostgreSQL)
- Full list of table names discovered across all schemas
- Ask the model to describe what this data source likely contains and how an analyst might use it

**Display:** A new card on `sources/source_detail.html` showing the insight text

### Implementation steps

- [x] Create `prompts/source_insights.py` with system message, model, max tokens, and `build_source_overview_prompt(source: Source) -> str`
- [x] Add `generate_source_overview(source: Source) -> str` to `BaseService` and both provider implementations
- [x] Update `sync_source` view in `apps/sources/views.py` — after sync completes and tables are saved, check if a source-level insight exists; if not, generate one
- [x] Add source overview insight card to `sources/source_detail.html`

---

## MVP Notes
- [x] Have claude help me update table prompt, be descriptive, dont reference row counts, don't reference a data analyst ("a data analyst would use this...") instead just describe how the data 
  could be used
- [x] Delete the existing source data and re-sync to see if the prompt is working


Note to self: use branch review skill before merging to main. And then create a new branch for the next item

- Sync LLM calls only (no Celery, no background tasks)
- One table at a time (no batch generation)
- InsightBuilder and cross-source insights are deferred

---

## Branch Review Notes (feature/insights-app)

All checklist items above are implemented and verified. Post-merge cleanup items:

- **Invalid OpenAI model name** — `"gpt-5.4-mini"` in `prompts/table_insights.py` and `prompts/source_insights.py` is not a real model ID. Fix before enabling the OpenAI provider path (e.g. `"gpt-4o-mini"`).
- **InsightDetailView target type** — `context['table']` in `apps/insights/views.py` and the matching template link in `insight_detail.html` assume the target is always a Table. Source-overview insights will render incorrectly. Rename the key and add a type branch in the template.
- **`print()` in exception handlers** — `apps/catalog/views.py` and `apps/sources/views.py` use `print()` for LLM errors. Replace with `logging.getLogger(__name__).exception()`.
- **Unsanitised markdown** — `render_markdown` filter passes LLM output through `mark_safe` without HTML sanitisation. Add `bleach` or similar before shipping to production.
- **Unpinned dependencies** — `openai`, `anthropic`, `psycopg2-binary`, `markdown` in `requirements.txt` have no version pins.