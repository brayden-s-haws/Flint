# Testing Plan

Write tests after the MVP is functionally complete. Focus on the flows that would break silently — auth, form validation, redirects, and anything touching the database.

Use Django's `TestCase` and `Client` throughout. No external testing libraries needed for MVP.

---

## apps.users

**Registration**
- GET `/auth/register/` returns 200
- POST with valid data creates a user, logs them in, and redirects
- POST with mismatched passwords returns 200 with non-field error
- POST with duplicate email returns 200 with field error
- POST with missing fields returns 200 with field errors

**Login**
- GET `/auth/login/` returns 200
- POST with valid credentials returns 302 and sets session
- POST with bad password returns 200 with non-field error
- POST with unknown email returns 200 with non-field error
- POST with `next` parameter redirects to `next` after login

**Logout**
- POST `/auth/logout/` clears session and redirects

---

## apps.accounts

_(fill in once accounts views are built)_

---

## apps.sources

_(fill in once sources views are built)_

- Source creation with valid credentials
- Source creation with missing fields
- Connection test — success and failure cases
- Sync trigger

**Scheduled syncs** (see `devdocs/featuredocs/scheduled-syncs.md`)

- **Unit:** `create_or_update_source_schedule` creates exactly one `PeriodicTask`, one `CrontabSchedule` (or reuses an existing matching one), and one `SourceSchedule`. Calling it again with a new frequency updates the same rows rather than creating duplicates.
- **Unit:** `disable_source_schedule` sets both `SourceSchedule.is_enabled=False` and `PeriodicTask.enabled=False`. Re-running `create_or_update_source_schedule` re-enables both.
- **Unit:** `toggle_source_schedule` flips `is_enabled` on both `SourceSchedule` and `PeriodicTask` and returns the pre-toggle state as `was_paused`. Raises `SourceSchedule.DoesNotExist` when called on a source with no schedule (toggle has no idempotent no-op).
- **Unit:** `delete_source_schedule` deletes both `SourceSchedule` and `PeriodicTask`. Idempotent no-op when no schedule exists.
- **Unit:** Deleting a `Source` deletes the linked `PeriodicTask` via the `post_delete` signal on `SourceSchedule`. No orphan rows.
- **Unit:** `run_scheduled_sync(source_id)` creates a `SourceSyncLog` with `status='running'` and enqueues `sync_source_task`. Use `CELERY_TASK_ALWAYS_EAGER=True` in test settings (per the celery-and-redis-setup notes). Defensive bail paths: returns early on `Source.DoesNotExist`, missing schedule, or disabled schedule.
- **Integration:** Account A cannot create/toggle/delete a schedule on account B's source. Hit `schedule_create`, `schedule_toggle`, `schedule_delete` with another account's `pk` and expect 404.
- **Integration:** `schedule_create` view enqueues an immediate sync when `created=True` (first-time setup) AND when `was_paused=True` (resume from paused). Pure frequency changes on an already-enabled schedule do NOT trigger an immediate sync.
- **Integration:** `SourceDetailView.get_context_data` populates `schedule`, `next_run`, `frequency_display`, and `schedule_form` correctly for both empty and configured states. `next_run` is timezone-aware; `frequency_display` falls back to `schedule.get_frequency_display()` when `cron_descriptor` raises.

**Source delete — insight cleanup** (see `devdocs/featuredocs/source-delete-insight-cleanup.md`)

The `cleanup_insights_on_source_delete` `pre_delete` signal on `Source` hard-deletes insights orphaned by the delete (catalog/sync rows cascade at the DB level, but insights attach via the generic `InsightTarget` FK which has no cascade).

- **Unit:** Deleting a source removes its `source_overview` insight (targeted at the source via `content_type=Source, object_id=source.pk`).
- **Unit:** Deleting a source removes its `use_case_suggestion` insights (targeted at the source).
- **Unit:** Deleting a source removes the `table_description` insights for every table under that source (targeted at the tables via `content_type=Table`).
- **Unit:** No orphaned `InsightTarget` rows remain after the source is deleted (cascade off the deleted `Insight` rows).
- **Integration:** Tenancy boundary — deleting account A's source does not delete account B's insights, even when a stale `object_id` collides. The signal scopes by `account=instance.account`.
- **Unit:** Insights belonging to a *different* source (same account) are left intact.

---

## apps.catalog

_(fill in once catalog views are built)_

- Schema/table/column list views return 200
- Views are scoped to the correct account (no cross-tenant leakage)

**TableStatistics**
- Sync creates a `TableStatistics` record linked to the correct `Table`
- PostgreSQL connector returns `column_stats` in the expected shape
- `TableStatistics` model defaults (null rates, row count) are set correctly when stats are missing or partial

---

## apps.insights

_(fill in once insights views are built)_

- Insight generation triggers LLM call (mock the LLM in tests)
- Insight list and detail views return 200

**Cross-Source Discovery** (see `devdocs/featuredocs/agentic-cross-source-discovery.md` — Phase 1: manual pair trigger + accept/dismiss)

Mock the LLM service everywhere — patch `apps.insights.services.provider.get_service` (or the three `discover_cross_source_relationships` / `generate_cross_source_hypotheses` / `generate_cross_source_use_case` methods) so no network calls happen. Use `CELERY_TASK_ALWAYS_EAGER=True` for the task/view tests.

_Pipeline + storage_
- **Unit:** `run_discovery_for_pair(source_a, source_b)` with a mocked service creates one `Insight(insight_type='cross_source_use_case', status='pending_review')` per surviving hypothesis, each with exactly **two** `InsightTarget` rows (one GenericFK per source), all scoped to `source.account`; returns the count persisted.
- **Unit:** `_flatten_and_rank_relationships` — join opportunities rank above semantic overlaps; confidence high/medium/low → 3/2/1; unknown/missing confidence → 0; the `_rank` scratch key is stripped from both inputs and outputs; a missing `join_opportunities` or `semantic_overlaps` key does not raise.
- **Unit:** Fan-out caps — Step 4 runs on at most the top 5 ranked relationships; at most 5 hypotheses survive to Step 6, sorted by `specificity_score` (missing/None coerced to `0.0`, does not crash the sort).
- **Unit:** Per-item isolation — an exception in Step 4 or Step 6 for one item is logged and skipped (`continue`) without sinking the run; the returned count reflects only insights actually persisted.
- **Unit:** Non-destructive regeneration — running the pipeline again for the same pair **appends** new insights and never deletes prior `cross_source_use_case` rows (no delete step).
- **Unit:** `_store_cross_source_use_case` is atomic — a failure mid-store never leaves an `Insight` with fewer than its two `InsightTarget`s (`transaction.atomic`).

_Celery task_
- **Unit:** `run_cross_source_discovery_task(account_id, a_id, b_id)` loads both sources scoped to `account_id` and calls `run_discovery_for_pair`. A source id belonging to another account raises `Source.DoesNotExist`; the task logs and bails **without creating insights** (tenancy guard — last line of defense behind the view).

_Views_
- **Integration:** `run_cross_source_discovery` happy path — POST enqueues the task and returns the results partial with `running=True`.
- **Integration:** `run_cross_source_discovery` rejections — **400** for a self-pair (`source_a == source_b`) and for either source not synced (`first_synced_at is None`); **404** for a source belonging to another account (via `get_object_or_404` tenancy scope — cross-account is 404, *not* 400).
- **Integration:** Per-pair rate limit — a `cross_source_use_case` insight linked to **both** sources created in the last 24h → **400**; assert it does **not** trip when only one of the two sources matches a recent run; assert a **dismissed** insight for the pair still rate-limits (the guard deliberately counts dismissed — "a run happened").
- **Integration:** `accept_agent_insight` — flips `pending_review` → `active` and returns the card partial; **400** when status is not `pending_review` (double-click / already-dismissed); **404** for another account's insight and for a non-`cross_source_use_case` insight (the `insight_type` scope on the lookup).
- **Integration:** `dismiss_agent_insight` — flips → `dismissed` and returns an **empty body** (HTMX swaps the card away); same `pending_review` / account / `insight_type` guards as accept.
- **Integration:** `CrossSourceDiscoveryView.get_queryset` — lists only `cross_source_use_case`, **excludes** `dismissed`, newest-first; `?source=<id>` filters to insights linked to that source; `?q=` searches `text`; account-scoped (account B's insights never appear).
- **Integration:** `cross_source_discovery_status` — `running=True` while the task is unfinished, flips to `False` once `AsyncResult(task_id).ready()`; account-scoped queryset.
- **Integration:** Dashboard `cross_source_insight_count` counts `cross_source_use_case` **excluding** `dismissed`, account-scoped.

_Tenancy boundary (required)_
- Account A cannot accept or dismiss account B's cross-source insight (404).
- Account A's discovery list and dashboard count never include account B's insights.

---

## Notes

- Use `Client.force_login()` to skip auth setup in tests that aren't testing auth itself
- Mock external calls (LLM APIs, database connectors) with `unittest.mock.patch`
- Test multi-tenancy boundaries: a user from account A should not see account B's data