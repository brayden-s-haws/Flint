# Feature: Async Intra-Source Use-Case Generation + Non-Destructive Regeneration

**Source:** `devdocs/appdocs/post_mvp.md` — build order item **11b** ("Convert intra-source use-case generation to async + make regeneration non-destructive — `insights`"), plus the `sources — Intra-Source Suggested Use Cases` section (the feature being modified).
**Status:** Not started
**Target phase:** Post-MVP Phase 3 (build order item 11b — scheduled immediately after cross-source discovery #11, which is complete).
**Suggested branch:** `feature/async-use-cases` — already checked out.

---

## Overview

`generate_intra_use_case_suggestions` (`apps/insights/views.py`) is the last insight generator still making its LLM call **synchronously inside the request/response cycle** — a heavy call (`USE_CASE_MAX_TOKENS=4000`, 4–6 use cases with SQL) that ties up a web worker and risks a gunicorn timeout. It also **deletes the existing use cases before** the LLM call, so a failed call leaves the user with nothing and throws away past suggestions.

This feature does two things: (1) move the generation into a Celery task using the established async-on-first-view pattern (spinner + poll), so the page never blocks; and (2) make regeneration **non-destructive** — append new suggestions newest-first instead of delete-then-create, in a fixed-height scrollable card. This brings intra-source use cases in line with the decisions already shipped for cross-source discovery (`devdocs/featuredocs/agentic-cross-source-discovery.md`).

---

## Dependencies

- [x] **Celery + Redis** — `devdocs/featuredocs/celery-and-redis-setup.md` complete; `@shared_task` + worker auto-discovery proven. A Redis **result backend** is configured (`CELERY_RESULT_BACKEND`, db 1) and shared across web/worker — available if the poll uses `AsyncResult`.
- [x] **Existing use-case service primitive** — `get_service('anthropic').generate_intra_source_use_case(source)` returns the list of use-case dicts (`{title, description, tables, starter_sql}`); reused **unchanged**. Prompt module `apps/insights/prompts/intra_source_use_cases.py` does not change.
- [x] **`Insight` statuses already exist** — `pending`, `active`, `failed` are already in `Insight.status` choices (added during async-table-descriptions). **No model change / migration needed.** Use cases use `insight_type='use_case_suggestion'` and store the payload in `structured_data`.
- [x] **`use_cases_status` poll endpoint + `_use_cases_section.html`** — `apps/insights/views.py::use_cases_status` (`GET /insights/use-cases/status/<source_id>/`) already renders the section via `build_use_cases_context(source)`; the section already self-polls while the **source overview** is `pending`. This feature extends the same endpoint/partial to also poll while **use-case generation** is in flight.
- [x] **Async pattern precedents** — `devdocs/featuredocs/async-table-descriptions.md` (pending-placeholder + `_insight_pending`/`_failed`/retry lifecycle) and `devdocs/featuredocs/agentic-cross-source-discovery.md` (spinner-while-running, non-destructive newest-first append, `hx-on::response-error` for surfacing 400s).

---

## Implementation Checklist

Single phase — this is one focused conversion, not a multi-phase build.

#### Tasks
- [ ] `apps/insights/tasks.py` — add `@shared_task def generate_use_cases_task(source_id: int, placeholder_id: int) -> None`. Loads the `Source` and the placeholder `Insight` by pk. Inside `try/except`: calls `get_service('anthropic').generate_intra_source_use_case(source)`, then for each returned use case creates an `Insight(account=source.account, text=use_case['title'], insight_type='use_case_suggestion', status='active', structured_data=use_case)` plus its `InsightTarget` (GenericFK to the source) — **appending, no delete**. On success **deletes the placeholder** row (its spinner is no longer needed). On exception flips the placeholder to `status='failed'`, `logger.exception(...)`, does not re-raise. IDs only per the `CLAUDE.md` Celery rule.
- [ ] Worker auto-discovery verified — `apps.insights.tasks.generate_use_cases_task` appears in the worker `[tasks]` block on startup.

#### Views & URLs
- [ ] **`generate_intra_use_case_suggestions` converted to async** (`apps/insights/views.py`). Keep the existing guards: source is account-scoped (`get_object_or_404`), a Source Overview must exist (`has_overview` → 400), and the 24h rate-limit guard. **Remove the delete block** (`existing_targets.delete()` + `Insight.objects.filter(...).delete()`) — this is the destructive-sequence bug flagged in the post_mvp bug bash. **Remove the synchronous `get_service(...).generate_intra_source_use_case(source)` call and the per-use-case create loop** — that logic moves to the task. Instead: create **one** placeholder `Insight(text='', insight_type='use_case_suggestion', status='pending', structured_data=None)` + its `InsightTarget`, enqueue `generate_use_cases_task.delay(source.id, placeholder.id)`, and return the `_use_cases_section.html` partial via `build_use_cases_context(source)` so the card swaps to the spinner state.
- [ ] **`build_use_cases_context(source)` updated** (`apps/insights/views.py`). The `use_cases` list must show only finished suggestions — filter to `insight__status='active'` (exclude the `pending` placeholder and any `failed` row), still ordered `-insight__created_at` (newest-first append). Add two flags derived from the `use_case_suggestion` targets for this source: `use_cases_generating` (a `status='pending'` placeholder exists) and `use_cases_failed` (a `status='failed'` placeholder exists). Keep the existing `use_case_rate_limited` / `use_case_hours_remaining` logic, but base "most recent" on `active` insights so a pending/failed placeholder doesn't skew the 24h window.
- [ ] **`use_cases_status` unchanged in signature** (`GET /insights/use-cases/status/<source_id>/`) — it already re-renders `_use_cases_section.html` via `build_use_cases_context`. It now also serves the use-case generation poll (the partial decides when to keep polling). No URL change.
- [ ] **Retry path** — decide between (a) reusing the Generate/Regenerate button from the `failed` state (re-enqueues via the same view, subject to the rate-limit guard), or (b) a dedicated retry that re-enqueues `generate_use_cases_task` for the existing placeholder (mirrors `insight_retry`). Note the choice in the section template. No new model either way.
- [ ] All touched views remain `@login_required` and account-scoped; the POST generator keeps `@require_POST`.

#### Templates
- [ ] **`templates/sources/_use_cases_section.html` — self-poll while generating.** The root `#use-cases-section` div currently adds `hx-get`/`hx-trigger="every 2s"`/`hx-swap="outerHTML"` only when `source_overview_insight.status == 'pending'`. Extend the condition so it **also** polls when `use_cases_generating` is true (poll target stays `use_cases_status`). Follow the persistent-spinner lesson from cross-source discovery: render an always-visible `animate-spin` SVG for the generating state, **not** the `htmx-indicator` component (which flashes on each poll).
- [ ] **Spinner / generating state** — when `use_cases_generating`, show a "Generating use case suggestions…" spinner block at the top of the card (existing suggestions, if any, still render below since regeneration is non-destructive).
- [ ] **Failed state** — when `use_cases_failed`, show an error message + a Generate/Regenerate (or Retry) control per the retry decision above.
- [ ] **Scrollable card (space-constrained, unlike the cross-source dedicated page).** Wrap the now-growing `use_cases` list in a fixed-height scroll container — `max-h-*` + `overflow-y-auto` — same pattern as the Sync History card, so the card doesn't grow unbounded as suggestions accumulate across regenerations.
- [ ] **Non-destructive, newest-first render** — the list iterates the `active` `use_cases` (already ordered newest-first), so a regenerate appends new cards to the top with prior suggestions preserved below.
- [ ] **(Optional) Surface generator 400s** — the generate/regenerate form posts via HTMX; if the rate-limit/overview-missing 400s should be visible (htmx doesn't swap non-2xx by default), mirror the `hx-on::response-error` → error-line pattern from `templates/insights/cross_source_discovery.html`.

#### Wiring
- [ ] No new URLs required (reuses `generate_use_cases` + `use_cases_status`); `apps/insights/urls.py` already has `app_name = 'insights'`. If a dedicated retry route is chosen, register it here.
- [ ] No `Flint/urls.py` change — `apps.insights.urls` is already included.

#### Tests *(deferred to the Phase 6 testing pass #24 — write up in `devdocs/testing.md` under `apps.insights`)*
- [ ] `generate_use_cases_task` (mock `get_service`, `CELERY_TASK_ALWAYS_EAGER=True`) creates one `active` `use_case_suggestion` Insight + `InsightTarget` per returned use case, scoped to the source's account, and **deletes the placeholder** on success.
- [ ] Task failure flips the placeholder to `failed` and creates no use-case rows.
- [ ] Regeneration is **non-destructive** — a second run appends and never deletes prior `use_case_suggestion` insights.
- [ ] The generate view rejects (400) when no Source Overview exists and when rate-limited; enqueues (does not call the LLM inline) on the happy path.
- [ ] Tenancy: account A cannot trigger or poll account B's source use cases (404).

---

## Key Design Decisions

- **Single pending placeholder as the in-flight marker (matches post_mvp 11b's "create pending placeholder insights").** Use cases arrive as a *batch* from one LLM call (N unknown until it returns), so — unlike table descriptions (one insight per table) — we create exactly **one** `pending` placeholder to represent "a generation is running," not one-per-result. The task creates the real `active` rows and deletes the placeholder on success. This gives idempotency (a pending placeholder means don't re-enqueue), a visible `failed` state with retry, and reuses the existing `use_cases_status` poll — the same "one field on one existing model" reasoning async-table-descriptions used. *(Alternative considered: the cross-source `task_id` + `AsyncResult(...).ready()` running flag. It works, but it can't represent a per-generation failure as a visible, retryable row, which the placeholder does for free. Flagged as the fallback if the placeholder approach gets awkward.)*
- **Non-destructive regeneration (mirrors the cross-source decision).** Never delete existing use cases before generating. Append new ones and render newest-first (`order_by('-created_at')`). Fixes the destructive-sequence bug (a failed LLM call currently wipes the card) and preserves suggestion history.
- **Rate-limit purpose shifts.** Keep the 24h regenerate guard, but its job is now "avoid runaway LLM cost," not "avoid overwriting" (there's nothing to overwrite anymore).
- **Scroll container because this lives in a space-constrained card**, unlike cross-source discovery's dedicated full page. The growing list gets `max-h-*` + `overflow-y-auto` instead of unbounded growth.
- **Source Overview stays a prerequisite.** The existing gate (generate use cases only after a Source Overview exists) is unchanged.
- **Service primitive unchanged.** `generate_intra_source_use_case(source)` and its prompt module are reused as-is; only the *call site* moves from the view to the task.

---

## Notes

- **This is the documented "migrate per-feature when revisited" step** from `architecture.md` and called out in `async-table-descriptions.md` ("The use-case suggestion path … is still synchronous; converting it is a separate consideration when that feature gets revisited"). This feature is that revisit.
- **Stale `pending` placeholder risk.** If the worker dies mid-task, the placeholder is stuck at `pending` and the card polls forever. Same risk/mitigations as async-table-descriptions (a periodic sweep flipping old `pending` → `failed`, or an age check on read) — defer unless it bites; document and move on.
- **The `use_cases` list must exclude the placeholder.** Because the placeholder is a `use_case_suggestion` insight with empty `structured_data`, `build_use_cases_context` must filter the rendered list to `status='active'` or the card will try to render a blank card and the rate-limit "most recent" logic will read the placeholder's timestamp. Called out in the Views checklist.
- **No model or migration.** `pending`/`active`/`failed` already exist on `Insight.status`; `use_case_suggestion` already exists on `insight_type`. Confirmed in `apps/insights/models.py`.
- **Open question (retry UX):** should a `failed` generation offer a one-click Retry (re-enqueue for the existing placeholder, like `insight_retry`) or just fall back to the normal Generate/Regenerate button (subject to the rate limit)? Decide during the template build; noted in the Views checklist.