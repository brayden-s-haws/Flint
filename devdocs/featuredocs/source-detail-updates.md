# Feature: Source Detail Updates

**Source:** `devdocs/appdocs/post_mvp.md` — build order item **10b** ("Source Detail Updates"), comprising sub-items 10c (async-on-first-view for Source Overview), 10d (two-column layout), and 10e (reorder Source Overview above Schemas & Tables)
**Status:** Complete — 10c (async Source Overview), 10d (two-column 3/5 + 2/5 layout), 10e (reorder), the table-detail card reorder, the LLM prompt heading removal, and the use-cases-gate-vs-async-overview fix are all built and verified in the browser.
**Target phase:** Post-MVP Phase 3 (sequenced immediately after Scheduled Syncs, before Agentic Cross-Source Discovery)

---

## Overview

Three related polish items on `sources/source_detail.html`:

1. **10c — Async-on-first-view for Source Overview.** Today the Source Overview is generated inline at the tail of `sync_source_task` (`apps/sources/tasks.py:64-73`). The sync-status poller flips to `HX-Refresh` as soon as `sync_log.status='success'` (saved at line 63) — *before* the LLM call at line 69 has finished. The user refreshes to "No overview yet." and must reload the page manually a few seconds later to see the generated text. This sub-task converts source-overview generation to the same async-on-first-view pattern that already works for table descriptions: create a `pending` Insight at enqueue time, render a spinner that polls a status endpoint, swap to content when the worker completes. The sync spinner stays unchanged.
2. **10d — Two-column layout.** Put four cards in a two-column grid: Source Overview and Schemas & Tables in the wider left column, Sync Schedule and Sync History in the right-hand sidebar. Suggested Use Cases sits full-width *below* the grid (it benefits from the room — the cards are wide). The page header and the source-type info banner stay full-width above the columns.
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
- [x] Multi-tab idempotency — the lookup-and-create guard lives in `sync_source_task` and the detail view never creates an overview insight, so concurrent page loads can't enqueue duplicate `generate_source_overview_task` calls.

---

### Sub-task 10d — Two-column layout

#### Templates

- [x] **Restructured `templates/sources/source_detail.html`** below the header / action buttons / demo banner / source-type info block into a two-column grid. **Final layout differs from the earlier full-width-Use-Cases plan** — see the layout note below.
  - Outer grid wrapper: `<div class="grid grid-cols-1 lg:grid-cols-5 gap-6">` (mobile collapses to single column; desktop splits **3/5 + 2/5**).
  - **Left column** (`<div class="lg:col-span-3">`):
    1. Source Overview (`{% include 'sources/_source_overview_section.html' %}`) — order set by 10e
    2. Schemas & Tables card (inline, unchanged)
    3. Suggested Use Cases (`{% include 'sources/_use_cases_section.html' %}`)
  - **Right column** (`<div class="lg:col-span-2">`):
    1. Sync Schedule (`{% include 'sources/_schedule_section.html' %}`)
    2. Sync History card (inline, unchanged — keeps its `id="sync-history"` root)
  - **No `space-y-6` on the columns** — each card already carries `mb-6`, so adding `space-y-6` doubled the gap. Spacing is left to the cards' own `mb-6`.
- [x] **Use Cases moved into the left column, not a full-width row.** The original plan put Use Cases full-width below the grid. In practice the Sync History card makes the right column tall, so a full-width row under a tall grid left the page lopsided. Stacking Use Cases in the left column (under Schemas & Tables) balances the two columns' heights. The grid now holds all content; there is no full-width row.
- [x] **Sync History and Schemas & Tables left inline** — the optional extraction into `_sync_history_section.html` / `_schemas_section.html` was skipped to minimise churn. `_sync_history.html` is unchanged, so the `hx-swap-oob="true"` target `id="sync-history"` (from `_sync_status.html`) still resolves regardless of column placement.
- [x] **Schedule card buttons fixed for the narrow sidebar.** In `_schedule_section.html` the three actions (Change Frequency / Pause-Resume / Delete Schedule) were `flex items-center gap-2`, which squeezed them in the 2/5 column so the labels wrapped to uneven heights. Changed to `flex flex-col gap-2` with each control `w-full text-center` (+ `whitespace-nowrap` on the summary) → three equal-width stacked buttons.
- [x] Responsive check — single-column stack on mobile (sidebar drops below the left column), 3/5 + 2/5 grid on `lg:` and above.
- [x] **Sync History height capped.** Wrapped the `#sync-history` list in a `<div class="max-h-96 overflow-y-auto">` scroll container so a long sync history can't stretch the right column taller than the left. The wrapper sits *outside* `#sync-history`, so the `hx-swap-oob="true"` swap (which replaces `#sync-history` itself) leaves the scroll box intact — no change needed in `_sync_status.html`.

---

### Sub-task 10e — Reorder Source Overview above Schemas & Tables

- [x] Source Overview is the first card in the left column, Schemas & Tables second. Landed alongside the 10c wiring (the `_source_overview_section.html` include was placed above the Schemas block).
- [x] No view or context changes required.

---

## Key Design Decisions

- **Reuse the async-table-descriptions pattern, but not its Retry button.** The polling partial (`_insight_pending.html`), status view (`insight_status`), and `Insight.status` lifecycle were built generically — they key off `insight.pk` and `insight.status`, not `insight_type`. Source Overview reuses all of that. The Retry button, however, is intentionally not reused: Sync Now is the natural retry path for an overview (overview is a byproduct of sync, not a standalone artifact), so the failed state is a dead-end message and `insight_retry` stays scoped to table descriptions.
- **Sync Now becomes the retry path for a failed overview.** Concretely: when `sync_source_task` runs and finds an existing overview Insight in `status='failed'`, it deletes that Insight (the `InsightTarget` cascades) before creating a fresh `pending` one and enqueuing the task. This means a failed overview self-heals on the next user-initiated sync without any retry UI.
- **Source-overview generation moves out of `sync_source_task`.** Keeping it inline means the sync-status `HX-Refresh` would have to wait for the LLM call before flipping to success, which defeats the point of separating sync from LLM work. A separate task is cheaper, isolates failure modes (sync can succeed even if the LLM is down), and lets the spinner shape match table descriptions.
- **No new model fields.** `Insight.status='pending'` was added precisely so this kind of slot can render before the LLM call returns. The Source-Overview context never needed a model change; the previous design just hid the gap by running everything inside one task.
- **Two-column layout uses Tailwind's responsive grid, not custom CSS.** `grid grid-cols-1 lg:grid-cols-5` + `lg:col-span-3` / `lg:col-span-2` handles desktop / mobile (3/5 + 2/5 split) with zero JS and zero stylesheet additions. Consistent with the existing card-grid patterns used elsewhere in the app.
- **Use Cases in the left column, not full-width.** Originally planned as a full-width row below the grid; changed because the tall Sync History sidebar made a full-width row look unbalanced. Keeping Use Cases in the left column evens the two columns' heights and keeps all content inside one grid.
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

- [x] **Removed the "Table Metadata" heading** from the first card. The two `<p>` lines (table type, row count) remain — the card is now a bare info block matching the source-type card at the top of `source_detail.html`.
- [x] **Moved the Insights card block** up to sit between the heading-less Metadata card and the Columns card. Final sequence: Metadata → Insights → Columns → Statistics. Pure block move; no context/view/URL changes.
- [x] Confirmed async polling still works after the move — the `_insight_slot.html` include and its polling root travelled with the block; verified in the browser.
- [x] File is well-formed — single `</main>` and `{% endblock content %}`, no duplication.

## Follow-on — Strip the heading from the LLM prompts

Both card UIs already render their own section heading ("Source Overview", "Insights"), so the `## Title` the LLM emitted inside the generated text was redundant. Removed the heading from both prompts. **The few-shot examples mattered most** — deleting only the instruction line leaves the model copying the `##` titles in the examples, so all three heading sources had to go in each file.

- [x] **`apps/insights/prompts/source_insights.py`** — (1) dropped "headings and" from `SOURCE_OVERVIEW_SYSTEM_MESSAGE`; (2) changed "Use a short title (## heading) followed by 2 short paragraphs" → "Write 2 short paragraphs" and added "Do not include a title or heading."; (3) removed the `## E-Commerce Application Database` and `## HubSpot CRM` headings from the two few-shot examples. Left the bold-text guidance intact.
- [x] **`apps/insights/prompts/table_insights.py`** — same three edits: dropped "headings and" from `TABLE_DESCRIPTION_SYSTEM_MESSAGE`; removed the `## heading` clause from the instruction and added "Do not include a title or heading."; removed the `## Payment Transactions` and `## Actor-Film Relationships` headings from the examples.
- [x] **Verified by regenerating.** Source overview and table description both regenerate as paragraphs only — no `##` title in the generated text.

---

## Follow-on — Use Cases gate vs. async overview (bug fix)

**Bug found after 10c shipped.** On a freshly synced source, the Suggested Use Cases card showed "Source must be synced before use cases are generated." even though the sync had just run. Root cause: use-case generation needs the overview *text* as prompt input, so the gate keyed off `source_overview` (set only when the overview is `active`). With 10c the overview now generates **asynchronously**, so right after sync it's `pending` and `source_overview` is empty → the gate couldn't distinguish "never synced" from "overview still generating," and it never updated once the overview finished (the card was rendered once at page load).

Fixed with the same poll-and-swap pattern used elsewhere in this feature:

- [x] **`build_use_cases_context(source)` helper** added in `apps/insights/views.py` — single source of truth for the card's data (`source_overview`, `source_overview_insight`, `use_cases`, rate-limit fields). Both the new status endpoint and `generate_intra_use_case_suggestions` use it; the latter's bespoke context block (which omitted `source_overview_insight`) was replaced — without that, the post-generate re-render would have shown "sync first" again.
- [x] **`use_cases_status` view + `insights:use_cases_status` URL** — re-renders `_use_cases_section.html` for a source; tenant-scoped via `get_object_or_404(account=request.account)`. This is the poll target.
- [x] **`_use_cases_section.html` rewritten** — gate now branches on `source_overview_insight.status` into four states: no overview → "Sync this source…"; `pending` → "Use cases will be available once the Source Overview finishes generating…"; `failed` → "…Click Sync Now to try again."; `active` → the normal Generate / cards UI. The wrapper `#use-cases-section` carries `hx-get` polling **only while `pending`**, so it self-heals when the overview lands and stops polling once the returned section is no longer pending. Also fixed a pre-existing stray `</main>` and div-nesting in this partial.
- [x] `manage.py check` passes; verified in the browser — fresh sync shows the pending message and auto-swaps to the Generate button when the overview completes, no manual refresh.

---

## Follow-on — Sync-status partial leaked the history table into the header (bug fix)

**Bug found while testing schedules.** After clicking **Set Schedule** (which kicks off a first sync and redirects), the sync-history table briefly rendered in the page header next to the title/buttons, then snapped back to normal once the sync finished. Root cause: the header renders `_sync_status.html` while a sync is running (`source_detail.html:13-14`), but that partial was doing double duty — it carried both the `#sync-status` spinner *and* the `#sync-history` `hx-swap-oob` block (the full history table). The OOB block is only meaningful as part of an HTMX *response* (to swap the existing right-column history); statically `{% include %}`-ing it into the header dumped the whole table there and created a duplicate `id="sync-history"`. When the sync completed, the poller's `HX-Refresh` reloaded the page and the header reverted to the Sync Now button — hence the transient "jump."

Fixed by splitting the spinner (page-includable) from the OOB wrapper (response-only):

- [x] **`_sync_status.html`** trimmed to just the `#sync-status` spinner/error div — safe to `{% include %}` in the header.
- [x] **`_sync_status_response.html`** (new) = `{% include '_sync_status.html' %}` + the `#sync-history` `hx-swap-oob` block. This is what the endpoints return so the right-column history still updates live during polling.
- [x] **`sync_source` and `sync_status` views** now render `_sync_status_response.html` instead of `_sync_status.html`. The header include stays on the spinner-only `_sync_status.html`.
- [x] `manage.py check` passes; verified in the browser — Set Schedule no longer shows the history table in the header, and the running-sync spinner + live history updates still work.