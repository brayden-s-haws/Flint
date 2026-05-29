# Feature: Source Detail Updates

**Source:** `devdocs/appdocs/post_mvp.md` — build order item **10b** ("Source Detail Updates"), comprising sub-items 10c (async-on-first-view for Source Overview), 10d (two-column layout), and 10e (reorder Source Overview above Schemas & Tables)
**Status:** In progress — 10c (async Source Overview) complete and verified; 10e (reorder above Schemas & Tables) landed alongside it; 10d (two-column layout) and the table-detail follow-on still to do
**Target phase:** Post-MVP Phase 3 (sequenced immediately after Scheduled Syncs, before Agentic Cross-Source Discovery)

---

## Overview

Three related polish items on `sources/source_detail.html`:

1. **10c — Async-on-first-view for Source Overview.** Today the Source Overview is generated inline at the tail of `sync_source_task` (`apps/sources/tasks.py:64-73`). The sync-status poller flips to `HX-Refresh` as soon as `sync_log.status='success'` (saved at line 63) — *before* the LLM call at line 69 has finished. The user refreshes to "No overview yet." and must reload the page manually a few seconds later to see the generated text. This sub-task converts source-overview generation to the same async-on-first-view pattern that already works for table descriptions: create a `pending` Insight at enqueue time, render a spinner that polls a status endpoint, swap to content when the worker completes. The sync spinner stays unchanged.
2. **10d — Two-column layout.** Move the Sync Schedule card and the Sync History card into a right-hand sidebar column, leaving Source Overview, Schemas & Tables, and Suggested Use Cases stacked in the wider left column. The page header and the source-type info banner stay full-width above the columns.
3. **10e — Reorder.** Within the left column, Source Overview appears above Schemas & Tables (today the order is reversed).

All three changes are presentation/wiring only — no new model fields, no new connectors, no LLM prompt changes.

---

## Dependencies

- [x] **Celery + Redis** — `devdocs/featuredocs/celery-and-redis-setup.md`. Workers already pick up `apps.insights.tasks` and `apps.sources.tasks`.
- [x] **Async table descriptions pattern** — `devdocs/featuredocs/async-table-descriptions.md`. This feature reuses its `pending → active → failed` lifecycle, polling partial shape, and `HX-Refresh`-free swap mechanics. The Source Overview task is a near-copy of `generate_table_description_task` with a different service call.
- [x] **`Insight.status` lifecycle choices** — `pending` / `active` / `failed` already on the model (added in `apps/insights/migrations/0006_alter_insight_status.py`). No migration required.
- [x] **`Insight.insight_type='source_overview'`** — added during the in-flight rename in async-table-descriptions; already in use at `apps/sources/tasks.py:70` and queried at `apps/sources/views.py:126`.
- [x] **Existing `_sync_status.html` polling precedent** — same pattern, scoped to a single insight slot.

---

## Implementation Checklist

### Sub-task 10c — Async-on-first-view for Source Overview

#### Tasks

- [x] Add `apps/insights/tasks.py::generate_source_overview_task(insight_id: int) -> None` as a new `@shared_task`, sitting next to its sibling `generate_table_description_task` (both are LLM insight-generation tasks — keeping them in one module beats splitting by enqueue site, mirroring how `generate_table_description_task` lives in `insights` despite being enqueued from `catalog`). Mirror the sibling: load the `Insight` by pk, resolve the `Source` via the linked `InsightTarget` (`content_type=ContentType.objects.get_for_model(Source)`, `.target` GenericForeignKey), call `get_service('anthropic').generate_source_overview(source)` inside a `try/except`. On success set `text` + `status='active'`. On exception flip `status='failed'`, `logger.exception(...)`, do not re-raise. Missing-InsightTarget raises `DoesNotExist` outside the try. Requires `from apps.sources.models import Source` in `insights/tasks.py` — no circular import (`sources.models` imports neither tasks module; verified by importing both under `django.setup()`).
- [x] Update `sync_source_task` (`apps/sources/tasks.py`) to stop running the LLM call inline. Instead, after `sync_log.save()`:
  - Look up the existing overview `InsightTarget` with `.select_related('insight').first()`, scoped by `insight__insight_type='source_overview'` (the old `.exists()` check was unscoped and would have collided with use-case insights on the same source).
  - If the existing overview's `status='failed'`, delete the Insight (the `InsightTarget` cascades) and reset the local to `None` — this is the "Sync Now is the retry path" behaviour (see Decision below).
  - If no overview now exists, create the placeholder `Insight` (`text=''`, `status='pending'`, `insight_type='source_overview'`) and its matching `InsightTarget`, then enqueue `generate_source_overview_task.delay(insight.pk)`.
  - The existing `try/except` guarding the inline LLM call is removed — the new task owns failure handling. `sources/tasks.py` now imports the task via `from apps.insights.tasks import generate_source_overview_task` and no longer imports `get_service`.
- [x] Verify worker auto-discovery: `apps.insights.tasks.generate_source_overview_task` appears in the `[tasks]` block on worker startup.

#### Views & URLs

- [x] Reuse the existing `apps.insights.views.insight_status` view (`GET /insights/<insight_id>/status/`) — no new URL route required. The view already branches on `Insight.status` and returns the matching partial regardless of `insight_type`.
- [x] **Do not modify `insight_retry`.** Source Overview does not get a Retry button (see Decision below). The hard-coded `generate_table_description_task` dispatch in `insight_retry` stays as-is; it remains scoped to table descriptions only. Left untouched.
- [x] **Update `SourceDetailView.get_context_data`** (`apps/sources/views.py`). Added `context['source_overview_insight']` = the full `Insight` object (or `None`) for the new section's status branching. **Also kept `context['source_overview']`** = `target.insight.text` only when `status == 'active'` — this preserves the existing `_use_cases_section.html` gate contract (it only needs "is there usable overview text?"), so that template did not need to change. Both producers of `source_overview` (this view on page load, `generate_intra_use_case_suggestions` on regenerate) stay in agreement on the key.

#### Templates

- [x] **Create `templates/sources/_source_overview_section.html`** — the card wrapper for the Source Overview. Replaced the inline block at `templates/sources/source_detail.html:84-93`. Card body branches on `source_overview_insight`:
  - No insight (`{% if not source_overview_insight %}`) → "No overview yet." muted paragraph.
  - `status == 'pending'` → include `_insight_pending.html` (spinner).
  - `status == 'active'` → include `_insight_content.html` (`render_markdown` + View link).
  - `status == 'failed'` → inline muted-red "Overview generation failed. Click Sync Now to try again." **No Retry button.**
- [x] **Did not use `_insight_slot.html` as the dispatcher.** Branched the four states inline so the failed state stays button-less (the slot dispatcher routes failed → `_insight_failed.html`, which carries the Retry button + CSRF wiring we don't want here).
- [x] **Spinner label derived from `insight_type`** in `templates/insights/_insight_pending.html` — `{% if insight.insight_type == 'source_overview' %}Generating overview…{% else %}Generating description…{% endif %}`. **Changed from the original `label`-arg plan:** `insight_status` re-renders this partial on every 2s poll with only `{'insight': insight}` and no `label`, so a `label` default would have flipped back to "Generating description…" after the first poll. Deriving from `insight_type` is self-contained and stays correct across polls. Table-description call site unaffected (falls through to the else branch).
- [x] Confirmed `_insight_pending.html` and `_insight_content.html` render correctly inside the Source Overview card chrome; the `insight-slot-{{ insight.pk }}` polling root swaps cleanly pending → content.
- [x] **`_use_cases_section.html` left unchanged** — the dual-context-key approach above means its `{% if not source_overview %}` gate works as-is (`source_overview` is now text-only-when-active, exactly the truthiness the gate wants). The original plan to rewrite the gate is moot.

#### Wiring

- [x] **`source_detail.html` updated** — inline overview block removed; `{% include 'sources/_source_overview_section.html' %}` inserted **above** the Schemas & Tables card (this also lands sub-task 10e — Source Overview now precedes Schemas & Tables).

#### Manual verification

- [x] Happy path — synced a source with no overview → page refreshed on success → "Generating overview…" spinner appeared → overview markdown swapped in ~5–10s later with no manual refresh; polling stopped on swap.
- [x] Failed path — forced an exception in the task → "Overview generation failed. Click Sync Now to try again." rendered with no Retry button → Sync Now deleted the failed insight and regenerated successfully.
- [x] Multi-tab idempotency — opening the source detail twice during sync does not enqueue duplicate `generate_source_overview_task` calls (not yet explicitly tested; the lookup-and-create guard 
  lives in `sync_source_task`, the detail view never creates an overview insight).

---

### Sub-task 10d — Two-column layout

#### Templates

- [ ] **Restructure `templates/sources/source_detail.html`** below the existing header / action buttons / demo banner / source-type info block. Replace the current single-column stack of cards (lines 46–94) with a two-column grid:
  - Outer wrapper: `<div class="grid grid-cols-1 lg:grid-cols-3 gap-6">` (mobile collapses to single column; desktop splits 2/3 + 1/3).
  - **Left column** (`<div class="lg:col-span-2 space-y-6">`):
    1. Source Overview card (`{% include 'sources/_source_overview_section.html' %}`) — order set by 10e
    2. Schemas & Tables card (existing block from current lines 55–83, extracted unchanged)
    3. Suggested Use Cases (`{% include 'sources/_use_cases_section.html' %}`)
  - **Right column** (`<div class="space-y-6">`):
    1. Sync Schedule (`{% include 'sources/_schedule_section.html' %}`)
    2. Sync History card (existing block from current lines 47–54, extracted into its own partial or kept inline — see next item)
- [ ] **Extract Sync History card to `templates/sources/_sync_history_section.html`** (optional but recommended for parity with how Schedule and Use Cases are organised). The new partial wraps the existing `{% include 'sources/_sync_history.html' %}` in the card chrome (heading + border + padding) that today lives inline at `source_detail.html:47-54`. Note: do not change `templates/sources/_sync_history.html` itself — that partial is targeted by `hx-swap-oob="true"` from `_sync_status.html:19-21` and must keep its `id="sync-history"` root unchanged.
- [ ] **Extract Schemas & Tables card to `templates/sources/_schemas_section.html`** (also optional, same parity reasoning). Pure template move — no context changes.
- [ ] Verify the OOB swap in `_sync_status.html:19-21` (`<div id="sync-history" hx-swap-oob="true">`) still finds its target after the layout change — the `id="sync-history"` lives inside `_sync_history.html`, which is included inside whatever sidebar slot holds it. As long as `id="sync-history"` is somewhere on the page when the OOB swap fires, HTMX resolves it regardless of column placement.
- [ ] Responsive check at `sm`, `md`, `lg` breakpoints — single-column stack on mobile (sidebar drops below main content), two-column on `lg:` and above.

---

### Sub-task 10e — Reorder Source Overview above Schemas & Tables

- [ ] Within the left column built in 10d, the Source Overview card is the first child and Schemas & Tables is the second. (This is already specified in the 10d checklist above; calling it out as a discrete sub-task to match the post_mvp numbering.)
- [ ] No view or context changes required.

---

## Key Design Decisions

- **Reuse the async-table-descriptions pattern, but not its Retry button.** The polling partial (`_insight_pending.html`), status view (`insight_status`), and `Insight.status` lifecycle were built generically — they key off `insight.pk` and `insight.status`, not `insight_type`. Source Overview reuses all of that. The Retry button, however, is intentionally not reused: Sync Now is the natural retry path for an overview (overview is a byproduct of sync, not a standalone artifact), so the failed state is a dead-end message and `insight_retry` stays scoped to table descriptions.
- **Sync Now becomes the retry path for a failed overview.** Concretely: when `sync_source_task` runs and finds an existing overview Insight in `status='failed'`, it deletes that Insight (the `InsightTarget` cascades) before creating a fresh `pending` one and enqueuing the task. This means a failed overview self-heals on the next user-initiated sync without any retry UI.
- **Source-overview generation moves out of `sync_source_task`.** Keeping it inline means the sync-status `HX-Refresh` would have to wait for the LLM call before flipping to success, which defeats the point of separating sync from LLM work. A separate task is cheaper, isolates failure modes (sync can succeed even if the LLM is down), and lets the spinner shape match table descriptions.
- **No new model fields.** `Insight.status='pending'` was added precisely so this kind of slot can render before the LLM call returns. The Source-Overview context never needed a model change; the previous design just hid the gap by running everything inside one task.
- **Two-column layout uses Tailwind's responsive grid, not custom CSS.** `grid grid-cols-1 lg:grid-cols-3` + `lg:col-span-2` handles desktop / mobile with zero JS and zero stylesheet additions. Consistent with the existing card-grid patterns used elsewhere in the app.
- **Sync History stays in the sidebar despite being OOB-swap-targeted.** HTMX resolves `hx-swap-oob="true"` by `id` regardless of DOM position; the column move is safe as long as the `id="sync-history"` div is on the page when the swap fires.

---

## Notes

- **Context key shape change — two template sites.** The view rename from `source_overview` (string) to `source_overview_insight` (Insight) needs both `source_detail.html:87` (the overview card body, which is moving into `_source_overview_section.html` anyway) and `_use_cases_section.html:4` (the gate that decides whether to show "sync first" or the generate-use-cases form) to update. Grep the templates folder for `source_overview` before declaring this done in case another reference has slipped in.
- **Use case generation rate-limiting is unaffected.** The `use_case_rate_limited` / `use_case_hours_remaining` logic in `SourceDetailView.get_context_data` keys off `Insight.created_at` on use-case insights, not on the source overview. No changes needed there.
- **Stale `pending` overview rows.** Same risk as table descriptions: if the worker crashes mid-task, the Insight is stuck at `pending` and the page polls forever. The async-table-descriptions featuredoc punts on a beat-task janitor; this feature inherits the same punt — defer until it bites in practice. (Note: for Source Overview specifically, the user can also clear a stuck `pending` row by clicking Sync Now, since the delete-and-recreate guard treats any non-`active` overview as eligible for replacement — though only `failed` is explicitly handled in the checklist above. Decide during the build whether to extend the delete branch to also cover stale `pending` rows older than N minutes, or leave that to the future janitor.)
- **Tests.** The async-table-descriptions test guidance applies: `CELERY_TASK_ALWAYS_EAGER = True`, mock `get_service('anthropic')`, verify tenancy boundary on `insight_status` for `insight_type='source_overview'` rows. New behaviour to cover: (a) `sync_source_task` deletes a failed overview Insight and creates a fresh pending one; (b) `sync_source_task` does not touch an `active` overview Insight; (c) the use-cases gate hides the generate form when the overview is `pending` or `failed`.

---

## Follow-on — Table Detail: promote Table Description, strip the metadata heading

A sibling polish item on the *table* detail page (`templates/catalog/table_detail.html`), bundled into this branch since it's the same "reorder cards on a detail page" theme. Independent of the Source Detail sub-tasks above — do it after 10c/10d/10e land.

**Goal:** make the table detail page lead with metadata + description, matching the bare info-card style at the top of `source_detail.html`. Today the card order is Metadata → Columns → Statistics → Insights (`table_detail.html:13-96`). After this change it becomes **Metadata (heading removed) → Insights → Columns → Statistics**.

#### Templates

- [ ] **Remove the "Table Metadata" heading** from the first card (`table_detail.html:15`, the `<h2>…Table Metadata</h2>`). Leave the two `<p>` lines (table type, row count) so the card becomes a bare info block — the same treatment as the source-type/last-synced card at the top of `source_detail.html:34-44`, which has no heading.
- [ ] **Move the Insights card block** (currently `table_detail.html:83-96`) up so it sits **between** the (now heading-less) Metadata card and the Columns card. Final card sequence below the page header: Metadata → Insights → Columns → Statistics. Pure block move — no context, view, or URL changes.
- [ ] Confirm the async polling still works after the move — the `_insight_slot.html` include and its `insight-slot-{{ insight.pk }}` polling root live inside the Insights card and travel with it; relocating the parent `<div>` doesn't affect HTMX resolution.
- [ ] Sanity-check the file is well-formed afterward: exactly one `</main>` and one `{% endblock content %}` (an earlier garbled read of this file suggested corruption; the actual file at `feature/source-detail-updates` HEAD is clean — just verify nothing got duplicated during the block move).