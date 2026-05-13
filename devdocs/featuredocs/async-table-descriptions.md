# Feature: Async Table Description Generation

**Source:** `devdocs/appdocs/post_mvp.md` — build order item #8 ("Batch table description generation — `insights`") and the `insights` section bullet: "Batch insight generation — generate descriptions for all tables in a source at once (requires Celery)"
**Status:** Not started
**Target phase:** Post-MVP Phase 3 (build order item #8, immediately after Celery + Redis setup)

> **Scope pivot note (2026-05-10):** The original post_mvp bullet framed this as bulk fan-out generation for every table in a source. After thinking it through, that approach generates insights for tables the user may never view (wasteful) and forces a "click to continue" UX for large databases (annoying). This featuredoc replaces the bulk plan with an **async-on-first-view** design: keep the existing lazy-trigger pattern (insight generates the first time a user opens a table without one), but move the LLM call off the request cycle so the page renders immediately and the insight slot polls for completion. Same goal — solve the blocking wait — but only spends LLM tokens on tables a user actually cares about. The previous featuredoc `batch-table-descriptions.md` is superseded by this one.

---

## Overview

Today, opening a table that lacks an insight blocks the page render for 5–10 seconds while `TableDetailView.get_context_data` (`apps/catalog/views.py:47-60`) makes a synchronous Anthropic call. This feature keeps the lazy-on-first-view trigger but moves the LLM call into the Celery worker (added in the previous feature). The page renders immediately with the surrounding content (columns, statistics, source link); the insight slot shows a spinner that polls every 2s and swaps to the rendered description when the worker finishes.

Tables that nobody views still pay zero LLM cost — exactly the same as today. The change is purely a UX upgrade: no more blocking page loads.

---

## Dependencies

- [x] **Celery + Redis setup** — `devdocs/featuredocs/celery-and-redis-setup.md` complete; `@shared_task` pattern + worker auto-discovery already proven via `apps/sources/tasks.py::sync_source_task`.
- [x] **Existing single-table generation service** — `BaseService.generate_table_description(table)` (`apps/insights/services/base.py:13`) and the Anthropic implementation (`apps/insights/services/anthropic_service.py:19`) are reused unchanged. The prompt file `apps/insights/prompts/table_insights.py` does not need to change.
- [x] **`Insight` + `InsightTarget` (GenericForeignKey)** — already in place; this feature adds two new `status` choices to `Insight` (`pending`, `failed`) but does not introduce new models.
- [x] **HTMX polling pattern reference** — `apps/sources/views.py::sync_status` + `templates/sources/_sync_status.html` are the working precedent for `HX-Refresh`-on-success + attrs-dropped-on-terminal-error self-polling. This feature follows the same shape, scoped to the table's insight slot instead of a whole-page refresh.

---

## Implementation Checklist

### Phase 1 — Async lazy generation

#### Models

- [x] In `apps/insights/models.py`, extend `Insight.status` choices to include two new states (full list reordered into lifecycle order: `pending → active → failed → archived → deleted`):
  - `('pending', 'Pending')` — placeholder row written by the view at enqueue time; task is in flight
  - `('failed', 'Failed')` — task ran but the LLM call raised; user can retry
- [x] Migration `apps/insights/migrations/0006_alter_insight_status.py` generated and applied. Single `AlterField` on `Insight.status` — no other fields touched.

#### Tasks

- [x] `apps/insights/tasks.py` created with `@shared_task def generate_table_description_task(insight_id: int) -> None`. Loads Insight by pk, resolves the Table via `InsightTarget.objects.get(insight=..., content_type=ContentType.objects.get_for_model(Table))` and the `.target` GenericForeignKey field, calls `get_service('anthropic').generate_table_description(table)` inside a try/except. On success sets `text` + `status='active'`. On exception flips `status='failed'`, logs via `logger.exception(...)`, does not re-raise. Missing-InsightTarget raises `DoesNotExist` loudly (outside the try) — that's a programmer error path, not an LLM failure.
- [x] Worker auto-discovery verified — `apps.insights.tasks.generate_table_description_task` appears in the `[tasks]` block on worker startup.

#### Insight type rename: `'ai'` → `'table_description'` / `'source_overview'`

In-flight cleanup added while building this feature. The current `'ai'` `insight_type` value is too broad — it conflates table descriptions and source overviews into one category, which (a) breaks the insight-list type filter (one bucket holds two genuinely different kinds of insight), (b) forces existing code to disambiguate by looking at the linked `InsightTarget.content_type`, and (c) breaks the precedent set by `'use_case_suggestion'` (specific, descriptive). Doing it now means the new view code added in this feature writes the right type from the start instead of writing `'ai'` rows that have to be migrated later.

- [x] **Model:** added `('table_description', 'Table Description')` and `('source_overview', 'Source Overview')` to `Insight.insight_type` choices in `apps/insights/models.py`. `'ai'` retained in the list for transitional safety.
- [x] **Schema migration:** `0007_alter_insight_insight_type.py` generated and applied — single `AlterField` on `Insight.insight_type`.
- [x] **Data migration:** `0008_retype_ai_insights.py` — `RunPython` that walks `Insight.objects.filter(insight_type='ai')`, looks up the linked `InsightTarget.content_type_id`, and re-types based on the target model (Table → `'table_description'`, Source → `'source_overview'`). Reverse direction flips both new types back to `'ai'` via bulk `.update()`. Applied cleanly — post-migration count of `insight_type='ai'` rows is 0.
- [x] **Code updates** — four sites updated (originally inventoried as three; `sources/views.py` was missed in the initial sweep and discovered when source overview stopped rendering in the UI):
  - `apps/catalog/views.py:53` → writes `insight_type='table_description'` for new pending placeholders
  - `apps/sources/tasks.py:70` → writes `insight_type='source_overview'` for source-overview generation inside `sync_source_task`
  - `apps/insights/views.py:84` and `:118` → both checks now query `insight__insight_type='source_overview'`
  - `apps/sources/views.py:123` → source-detail view's overview lookup now queries `insight__insight_type='source_overview'`
- [x] **Verified** in the running app — worker restarted, new source-overview write produces `insight_type='source_overview'`, source-detail view renders the overview after the `sources/views.py` fix landed, insight list type filter shows the new buckets correctly.
- [x] **Optional follow-up migration:** once everything verifies, remove `'ai'` from the choices list. Deferred — no harm in leaving the legacy choice available, and it gives the data migration a 
  stable target if a row ever needs to be retried.

#### Views & URLs

- [x] **`TableDetailView.get_context_data` updated** in `apps/catalog/views.py:48-59`. Synchronous service call replaced with async-enqueue: existing `InsightTarget` query still runs first; if no insight exists, a placeholder `Insight` (`text=''`, `status='pending'`, `insight_type='table_description'`) is created with its matching `InsightTarget`, the task is enqueued via `generate_table_description_task.delay(insight.pk)`, and the placeholder is added to context. Idempotency guard (`if not context['insights']`) prevents duplicate enqueues across refreshes/tabs. `try/except` removed — the task owns failure handling. Unused `get_service` import removed.
- [x] **`insight_status` view added** in `apps/insights/views.py` — `GET /insights/<insight_id>/status/`. `@login_required`, tenant-scoped `get_object_or_404`. Branches on `insight.status`: `pending` → `_insight_pending.html`, `active` → `_insight_content.html`, `failed` → `_insight_failed.html`. Unexpected states return `HttpResponse(status=400)` so they fail loudly rather than masquerading as a failure.
- [x] **`insight_retry` view added** in `apps/insights/views.py` — `POST /insights/<insight_id>/retry/`. `@login_required` + `@require_POST`, tenant-scoped `get_object_or_404`. Guard returns 400 if `status != 'failed'`. Flips `status='pending'`, saves, re-enqueues `generate_table_description_task.delay(insight.id)`, returns the `_insight_pending.html` partial so HTMX swaps the failure slot back to the spinner.
- [x] URLs registered in `apps/insights/urls.py`: `insights:insight_status` and `insights:insight_retry`. Smoke-tested — pending insight at `/insights/<id>/status/` produces the expected `TemplateDoesNotExist` 500 (view + URL + ownership all working); bogus ID returns clean 404.

#### Templates

- [ ] Create `templates/insights/_insight_pending.html` — the polling partial. Single root `<div id="insight-slot-{{ insight.pk }}">` carrying `hx-get="{% url 'insights:insight_status' insight.pk %}"`, `hx-trigger="every 2s"`, `hx-swap="outerHTML"`. Renders an inline SVG spinner + "Generating description…" text styled to match the existing insight card visual (so the slot doesn't visually pop when content arrives).
- [ ] Create `templates/insights/_insight_content.html` — the final rendered insight. Root `<div id="insight-slot-{{ insight.pk }}">` with no HTMX attrs (polling stops naturally because the new root replaces the polling one). Renders `{{ insight.text|linebreaks }}` inside the same card chrome as the spinner partial.
- [ ] Create `templates/insights/_insight_failed.html` — error state. Root `<div id="insight-slot-{{ insight.pk }}">` with no HTMX attrs. Renders a red error message ("We couldn't generate a description for this table — try again") and a retry button (`hx-post="{% url 'insights:insight_retry' insight.pk %}"`, `hx-target="this"`, `hx-swap="outerHTML"`). The retry response swaps the failure partial back to the pending partial, and polling resumes.
- [ ] **Modify `templates/catalog/table_detail.html`** — locate the block that currently renders the insight inline. Replace it with a `{% include %}` that branches on `insight.status`:
  - On first page load, if `status='pending'` (just enqueued) → include `_insight_pending.html`
  - If `status='active'` (already complete from a previous visit) → include `_insight_content.html`
  - If `status='failed'` (previous attempt failed, no auto-retry) → include `_insight_failed.html`
  - The branching can live in the template via `{% if %}` or be pushed into a single dispatching partial (`_insight_slot.html` that itself does the `if/elif/else`). The dispatcher pattern is slightly cleaner if the insight gets rendered in more than one place later (it does — `insight_detail.html` may reuse it).

#### Wiring

- [ ] Confirm `apps/insights/urls.py` already has `app_name = 'insights'` set (it does — see `insights:list` / `insights:detail` references elsewhere).
- [ ] No changes needed to `Flint/urls.py` — `apps.insights.urls` is already included.

#### Manual verification

- [ ] On a table with no existing insight, open the detail page. Expect: page renders immediately (columns, stats, source link all visible); insight slot shows the spinner; worker log shows `apps.insights.tasks.generate_table_description_task[<id>]` received; ~5–10s later, slot swaps to the rendered description without a page reload.
- [ ] Refresh the page mid-generation. Expect: existing pending `Insight` is reused, spinner appears again immediately, **no second task is enqueued** (check worker logs — only one task processed). Spinner swaps to content once the original task completes.
- [ ] Open the same table in two browser tabs simultaneously (cold cache, no existing insight). Expect: the first request creates the pending row + enqueues one task; the second request finds the pending row and does not enqueue. Both tabs end up showing the same generated description.
- [ ] Force a failure (temporarily raise inside the Anthropic service before the API call) and reload a description-less table. Expect: spinner appears, ~2s later swaps to the failure partial with the retry button. Click retry: spinner returns, polling resumes, success or failure cycle plays out again.
- [ ] On a table that *already has* an `active` insight from before this feature, open the detail page. Expect: content renders immediately on first paint, no polling, no spinner flicker. (Regression check — the existing insight cache stays useful.)

---

## Key Design Decisions

- **Lazy-on-first-view stays.** Tables nobody views still cost zero LLM tokens. This is the philosophy of the rest of the product — metadata-only, on-demand intelligence — and changing it for bulk generation would have wasted spend on inert tables.
- **`Insight.status='pending'` is the in-flight signal.** Creating the placeholder row at enqueue time gives us idempotency across refreshes and tabs (anyone arriving sees `pending` → renders spinner → does not re-enqueue). The alternative (Redis cache lock) avoids the transient empty row but adds a TTL failure mode and a second source of truth. One field on one existing model wins.
- **`failed` is a visible state with a retry, not silent dropping.** A failed Anthropic call leaves a row the user can see and act on. Today's sync code silently swallows the exception in `TableDetailView` (`apps/catalog/views.py:59-60`); this is strictly better.
- **Polling per-insight-slot, not per-page.** The polling partial swaps its own `<div>`, leaving the rest of `table_detail.html` alone. No page reload on success means the user keeps their scroll position, expanded sections, etc.
- **No new model.** `BatchInsightRun` / `BatchInsightsRun` from the earlier draft is not needed — there's nothing to track that isn't already captured by `Insight.status`. The empty `BatchInsightsRun` skeleton has been removed from `models.py`.
- **Reuse the existing service primitive.** `generate_table_description(table)` is unchanged. The task is a thin wrapper that resolves the table from the insight's `InsightTarget`, calls the service, and persists.

---

## Notes

- **Polling cadence.** 2-second interval matches the sync-status precedent; at 5–10s of expected work, that's 3–5 polls per generation, each a single indexed DB lookup. Cheap. Raise to 3–5s later only if profiling shows it matters.
- **Stale `pending` rows.** If the worker crashes mid-task, an `Insight` could be stuck at `status='pending'` indefinitely — polling would never stop. Two mitigations to consider (defer unless it bites in practice): (a) a periodic Celery beat task that flips rows older than N minutes from `pending` → `failed`; (b) check `started_at` in the polling endpoint and flip on read. Neither is needed for the first cut; document the risk and move on.
- **Source overview generation still synchronous.** This feature converts only the table-description path. The source-overview LLM call inside `sync_source_task` (`apps/sources/tasks.py:64-73`) already runs in the worker, so it's not blocking the user anyway. The use-case suggestion path (`generate_intra_use_case_suggestions` at `apps/insights/views.py:78`) is still synchronous; converting it is a separate consideration when that feature gets revisited.
- **Tests.** Set `CELERY_TASK_ALWAYS_EAGER = True` in test settings so the task runs synchronously in-process. Mock `get_service('anthropic')` so no real LLM calls fire. Tenancy boundary: account A user cannot trigger or poll an account B insight (verify ownership checks on both `insight_status` and `insight_retry`).
- **Migration is a `choices=` change only.** Django requires a migration file for `choices` changes even though the DB schema doesn't change. The generated migration is safe and trivially reversible.
- **Open question: failed-insight cleanup.** Should a `failed` row be deletable from the UI (not just retryable)? Punt until a user complains.
