# Feature: Scheduled Syncs

**Source:** `devdocs/appdocs/post_mvp.md` — "core / infrastructure" (build order item #10)
**Status:** Not started
**Target phase:** Post-MVP Phase 3
**Suggested branch:** `feature/scheduled-syncs` (already checked out)

---

## Overview

Today every source sync is triggered manually from the source detail page. This feature lets a user attach a recurring schedule (hourly, daily, weekly, monthly) to any source so its catalog stays fresh without manual intervention. Schedules are defined per source, off by default, and configurable from the source detail page. The source detail page also surfaces the configured frequency above the sync history so the user can see at a glance how stale the data might be.

This is the first feature to make real use of Celery Beat, which was wired up as foundation in `devdocs/featuredocs/celery-and-redis-setup.md` but has no schedules attached yet. Scheduling is built on `django-celery-beat`'s DB-backed scheduler so users can add/edit/disable schedules without redeployment.

---

## Dependencies

- [x] Celery + Redis infrastructure — see `devdocs/featuredocs/celery-and-redis-setup.md`. Worker, beat, broker, and result backend are all configured.
- [x] `django-celery-beat==2.9.0` installed and migrated. Tables (`PeriodicTask`, `CrontabSchedule`, `IntervalSchedule`) exist in the DB. Beat scheduler set to `'django_celery_beat.schedulers:DatabaseScheduler'` in `Flint/settings.py`.
- [x] `apps/sources/tasks.py::sync_source_task(source_id, sync_log_id)` — the existing async sync task that will be invoked by the scheduled trigger.
- [x] `apps/sources/models.py::Source` and `SourceSyncLog` — the periodic task creates a new `SourceSyncLog` per run, mirroring the manual-trigger flow.
- [x] `apps/sources/views.py::SourceDetailView` — the page where the schedule UI will be added.
- [x] `cron_descriptor==1.4.5` already installed (transitive dep of `django-celery-beat`). Used in Phase 2 to render the frequency in plain English (e.g. `"At 06:00 AM, only on Monday"`).
- [x] `croniter==6.2.2` pinned in `requirements.txt` and installed. Needed for accurate next-run computation. Celery's built-in `crontab.remaining_estimate()` was tested and is *not* suitable for user display: it returned 3.4h when the actual next 6 AM fire was 19.5h away. It's an internal beat hint, not a next-fire calculator.
- [x] `celery -A Flint beat -l info` process running locally during dev. Added to the PyCharm `Dev Workflow` compound alongside the worker.

---

## Implementation Checklist

### Phase 1 — Schedule model + task wrapper

#### Models

- [x] `SourceSchedule` (new model in `apps/sources/models.py`) — one-to-one with `Source`. Fields:
  - `source = OneToOneField(Source, on_delete=CASCADE, related_name='schedule')`
  - `frequency = CharField` with choices `('hourly', 'Hourly'), ('daily', 'Daily'), ('weekly', 'Weekly'), ('monthly', 'Monthly')`
  - `is_enabled = BooleanField(default=True)` — lets the user pause without deleting
  - `periodic_task = OneToOneField('django_celery_beat.PeriodicTask', on_delete=SET_NULL, null=True, blank=True)` — the actual scheduler row managed by django-celery-beat; `blank=True` so Django forms/admin allow it empty (created lazily after the schedule row)
  - Inherits `TenantAwareModel` (so `account` FK + timestamps come for free)
- [x] `cron_expression` `@property` on `SourceSchedule` — returns the cron string by concatenating `self.periodic_task.crontab` fields in order. Returns `None` if `periodic_task` or `periodic_task.crontab` is missing. Single source of truth for the cron string consumed by `croniter` and `cron_descriptor`.
- [x] `Source.next_sync_at` is **not** added — derive it on the fly from `schedule.periodic_task.crontab` rather than denormalising.
- [x] Migration generated and applied (`apps/sources/migrations/0004_sourceschedule.py`).
- [x] Register `SourceSchedule` in `apps/sources/admin.py`.

#### Periodic task wrapper

- [ ] Add `run_scheduled_sync(source_id: int) -> None` to `apps/sources/tasks.py`. The task:
  - Loads `Source` by id and bails (logs) if the source no longer exists or its schedule is disabled (defensive — should be removed from beat already, but covers race).
  - Creates a new `SourceSyncLog(account=source.account, status='running', started_at=timezone.now())`.
  - Calls `sync_source_task.delay(source.pk, sync_log.pk)` — reuses the existing task body. **Do not** call `sync_source_task` synchronously inside `run_scheduled_sync`; keep the queue boundary so a long sync doesn't block beat from emitting the next tick.
  - Pass IDs only (per the Celery rule documented in `CLAUDE.md`).
- [ ] Register the task name in beat by giving the `PeriodicTask` row `task='apps.sources.tasks.run_scheduled_sync'` and `args=json.dumps([source.pk])` (django-celery-beat takes args as JSON strings).

#### Schedule helpers

- [x] Added `apps/sources/scheduling.py` with:
  - `FREQUENCY_TO_CRONTAB: dict[str, dict[str, str]]` mapping each frequency to the five `CrontabSchedule` fields. Defaults: hourly at minute 0 of every hour, daily 06:00, weekly Mondays 06:00, monthly 1st 06:00. Times in `settings.TIME_ZONE`.
  - `create_or_update_source_schedule(source: Source, frequency: str) -> tuple[SourceSchedule, bool]` — handles the `get_or_create` of the `CrontabSchedule`, the `PeriodicTask` row (`enabled=True`, correct `task`, `args`, `crontab`), and the `SourceSchedule` model wiring. Returns `(schedule, created)` so the caller knows whether this was a first-time enable (used to trigger the immediate sync — see next bullet). Also handles the rare `SET_NULL` recovery path where a `SourceSchedule` exists but its `periodic_task` was nulled out of band.
  - `disable_source_schedule(source: Source) -> None` — sets `SourceSchedule.is_enabled=False` and `PeriodicTask.enabled=False`. Idempotent no-op when no schedule exists. Keeps the row so re-enabling preserves the frequency choice.
  - `delete_source_schedule(source: Source) -> None` — deletes the `SourceSchedule` and its `PeriodicTask` (the orphaned `CrontabSchedule` can be left; django-celery-beat reuses identical crontabs). Idempotent no-op when no schedule exists.
  - Helpers use `try/except SourceSchedule.DoesNotExist` on the reverse one-to-one accessor — idiomatic Django and avoids the `getattr(..., None)` type-narrowing issue with `Any | None`.

#### Immediate sync on first enable

- [ ] In the `schedule_create` view (Phase 2), when `create_or_update_schedule` returns `created=True` **or** when re-enabling a previously paused schedule (`is_enabled` flipped from `False` to `True`), immediately enqueue `run_scheduled_sync.delay(source.pk)` so the user gets feedback now rather than waiting for the next cron boundary. Changing the frequency on an already-enabled schedule does **not** trigger an immediate sync — that would be surprising.
- [ ] Show a flash message confirming both actions: "Schedule set — first sync started now. Future runs: every day at 6:00 AM." (adapt copy per frequency).

#### Cascade on source delete

- [ ] When a `Source` is deleted, its `PeriodicTask` must go too (otherwise beat keeps firing for a missing source). The `OneToOneField` cascade handles `SourceSchedule`; add a `post_delete` signal on `SourceSchedule` (in `apps/sources/signals.py` — create if not present, wire from `apps.py::ready()`) that deletes the linked `PeriodicTask`. Verify by creating a schedule, deleting the source, confirming the `PeriodicTask` row is gone.

#### Dev workflow

- [x] Add `celery -A Flint beat -l info` to the PyCharm `Dev Workflow` compound so beat starts alongside worker, runserver, and Tailwind. Note this in `CLAUDE.md` "Common Commands" (beat command is already documented; just confirm it now must run for this feature).

### Phase 2 — UI: configure, view, change, disable

#### Forms

- [ ] `ScheduleForm` in `apps/sources/forms.py` — single radio/select field for `frequency` with the four choices. Apply the project Tailwind input classes per `CLAUDE.md` "Forms" standard (`w-full bg-flint-card border border-flint-border-em rounded-md px-3 py-2 text-sm text-flint-text focus:outline-none focus:ring-2 focus:ring-flint-orange`).

#### Views & URLs

- [ ] `schedule_create` — `POST /sources/<pk>/schedule/` — creates/updates schedule from `ScheduleForm`. Handles both first-time setup and frequency changes via the same endpoint. Redirects back to source detail (or returns HTMX partial — see template note below).
- [ ] `schedule_toggle` — `POST /sources/<pk>/schedule/toggle/` — flips `is_enabled` (and the underlying `PeriodicTask.enabled`). Pause/resume button.
- [ ] `schedule_delete` — `POST /sources/<pk>/schedule/delete/` — removes the schedule entirely. Separate from toggle so the user can clear out the frequency choice if they want a fresh setup.
- [ ] All three views use `@login_required` and scope `Source` lookup by `account=request.account` (mirrors the existing `test_connection` / `sync_source` pattern).
- [ ] Add URL patterns to `apps/sources/urls.py`:
  - `path('<int:pk>/schedule/', views.schedule_create, name='schedule_create')`
  - `path('<int:pk>/schedule/toggle/', views.schedule_toggle, name='schedule_toggle')`
  - `path('<int:pk>/schedule/delete/', views.schedule_delete, name='schedule_delete')`

#### Templates

- [ ] New partial `templates/sources/_schedule_section.html` — renders one of two states:
  - **No schedule set** — short copy ("This source has no schedule. Syncs run only when you click Sync Now.") + a "Set up schedule" button that reveals/links to the form.
  - **Schedule set** — shows the configured frequency in plain English ("Runs daily at 6:00 AM"), the next scheduled run time (derived from `periodic_task.crontab` via `croniter` or django-celery-beat's `schedule` helper), a "Change frequency" button, a "Pause / Resume" toggle button, and a "Remove schedule" button. If `is_enabled=False`, show a muted "Paused" badge next to the frequency.
- [ ] New partial `templates/sources/_schedule_form.html` — the `ScheduleForm` markup. Used both as initial form render and as the HTMX swap target when "Change frequency" is clicked.
- [ ] Edit `templates/sources/source_detail.html` — include `{% include 'sources/_schedule_section.html' %}` **directly above** the Sync History card (per the spec: "above the sync history display information on how often the sync runs"). Match the existing card styling (Tailwind `bg-flint-card`, border, rounded, etc. — copy from the use-cases section card).

#### Context

- [ ] Extend `SourceDetailView.get_context_data` to pass:
  - `schedule = getattr(source, 'schedule', None)` (the `SourceSchedule` if it exists, else `None`)
  - `next_run = <datetime>` — derive via `croniter(cron_expression, timezone.now()).get_next(datetime)`. Build the cron expression from the `CrontabSchedule` row (`f"{ct.minute} {ct.hour} {ct.day_of_month} {ct.month_of_year} {ct.day_of_week}"`). **Do not** use celery's `remaining_estimate` — verified inaccurate for user display.
  - `frequency_display = <str>` — human-readable string from `cron_descriptor.ExpressionDescriptor(cron_expression).get_description()` (e.g. "At 06:00 AM, only on Monday"). Falls back to `schedule.get_frequency_display()` only if `cron_descriptor` fails.

#### Settings & Wiring

- [x] Verify `'django_celery_beat'` is in `INSTALLED_APPS` (already added by celery-and-redis-setup — no change needed, but confirm).
- [x] No new middleware. No new env vars.

### Phase 3 — Tests & verification

- [ ] **Unit:** `create_or_update_schedule` creates exactly one `PeriodicTask`, one `CrontabSchedule` (or reuses an existing matching one), and one `SourceSchedule`. Calling it again with a new frequency updates the same rows rather than creating duplicates.
- [ ] **Unit:** `disable_schedule` sets both `SourceSchedule.is_enabled=False` and `PeriodicTask.enabled=False`. Re-running `create_or_update_schedule` re-enables both.
- [ ] **Unit:** Deleting a `Source` deletes the linked `PeriodicTask` (signal test). No orphan rows.
- [ ] **Unit:** `run_scheduled_sync(source_id)` creates a `SourceSyncLog` with `status='running'` and enqueues `sync_source_task`. Use `CELERY_TASK_ALWAYS_EAGER=True` in test settings (per the celery-and-redis-setup notes).
- [ ] **Integration:** Account A cannot create/toggle/delete a schedule on account B's source. Hit `schedule_create` with another account's `pk` and expect 404.
- [ ] **Manual end-to-end:**
  1. Set a schedule with frequency=`hourly` on a source. Confirm `PeriodicTask` row appears in admin.
  2. Restart beat (it picks up DB changes within 5s by default, but restart is faster).
  3. Wait for the next hour boundary (or temporarily set a 1-minute interval for testing — use a `CrontabSchedule` with `minute='*'`).
  4. Confirm a new `SourceSyncLog` appears in source detail with the same data as a manual sync, and beat logs show the task firing.
  5. Pause the schedule. Confirm no further runs after the next tick.
  6. Resume, then delete. Confirm the `PeriodicTask` row is gone from admin.

---

## Key Design Decisions

- **One schedule per source, not many.** The spec is explicit ("This should be defined at the source level"). Modelling as a `OneToOneField` keeps the UI and logic simple. Multi-schedule per source (e.g., "incremental hourly + full weekly") is a future enhancement, not in scope.
- **Use `django-celery-beat`'s DB scheduler, not `CELERY_BEAT_SCHEDULE` in settings.** Already configured in `Flint/settings.py` as `'django_celery_beat.schedulers:DatabaseScheduler'`. Static beat schedules in settings would require redeploys; DB schedules let the user (or admin) change frequencies live. This was an explicit decision in the celery-and-redis-setup featuredoc with this feature in mind.
- **Wrap `sync_source_task` rather than scheduling it directly.** Beat can only call tasks with statically-known args. `sync_source_task` needs both `source_id` and `sync_log_id`, but `sync_log_id` is per-run. The wrapper (`run_scheduled_sync`) takes only `source_id`, creates the `SourceSyncLog`, then delegates. Keeps the existing sync path unchanged so manual and scheduled syncs share the same code below the wrapper.
- **Frequency choices are coarse-grained for MVP.** Hourly / daily / weekly / monthly cover the realistic catalog-refresh cadence and avoid building a cron-expression UI. If users later want finer control (e.g., "every 6 hours" or "weekdays only"), promote `frequency` to a richer form rather than exposing raw cron syntax.
- **Pause vs. delete.** Keeping the schedule row when paused (with `is_enabled=False`) preserves the user's frequency choice so resuming is one click. Deleting removes both the `SourceSchedule` and the `PeriodicTask` so beat stops emitting.
- **Immediate sync on first enable (and on resume).** When a user enables a schedule for the first time — or resumes one after pausing — fire one sync right away rather than making them wait for the next cron boundary. Pure frequency changes (already-enabled → still-enabled, just different cadence) do **not** trigger an immediate sync. Gives the user instant feedback that the schedule is wired up without surprising them mid-day when they tweak the frequency.
- **Don't store `next_run_at` on the model.** Derive it on the fly from the `CrontabSchedule`. Storing it would create a denormalisation problem the first time beat runs slightly off-schedule.
- **Schedule UI lives above sync history, not in a separate page.** Per the spec. Keeps the source detail page as the single surface for "what's happening with this source."

---

## Notes

- **`croniter` is required and must be added to `requirements.txt`.** Investigated alternatives before committing to a new dep: Celery's `crontab.remaining_estimate()` was tested against a 6 AM schedule from a 10:30 AM "now" and returned 3.4 hours instead of the correct 19.5 hours — it's an internal beat hint, not an accurate next-fire calculator. `django-celery-beat`'s `DatabaseScheduler` has no public next-fire helper either. `cron_descriptor` (already transitively installed) only handles human-readable strings, not next-fire datetimes. Croniter is the right tool.
- **Beat reload interval:** by default, `DatabaseScheduler` polls the DB every 5s for schedule changes. New/edited schedules don't take effect instantly. Acceptable for this feature; mention in the UI copy if it surprises users ("changes take effect within a minute").
- **Timezone handling:** schedules execute in `CELERY_TIMEZONE` (set to `TIME_ZONE` from settings during celery-and-redis-setup). All accounts share this timezone for now; per-account timezone is out of scope.
- **Don't expose the underlying `PeriodicTask` to users.** The Django admin will show it (and that's useful for debugging), but the user-facing UI only talks about "frequency" — not about beat tasks, crontabs, or schedules-as-rows. Keep the abstraction clean.
- **Concurrency safety:** if a sync is already running when the schedule fires, `run_scheduled_sync` will enqueue a second one. That's probably fine — Celery serializes them, the second just waits. If it becomes a problem, add a guard: skip the run if the most-recent `SourceSyncLog` for this source has `status='running'`.
- **Out of scope:** schedule history (which runs were scheduled vs. manual), schedule conflict detection (e.g., overlapping incremental + full syncs), notification emails when a scheduled run fails, per-account timezone selection.