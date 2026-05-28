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

---

## Notes

- Use `Client.force_login()` to skip auth setup in tests that aren't testing auth itself
- Mock external calls (LLM APIs, database connectors) with `unittest.mock.patch`
- Test multi-tenancy boundaries: a user from account A should not see account B's data