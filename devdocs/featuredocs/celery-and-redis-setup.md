# Feature: Celery + Redis Setup

**Source:** `devdocs/appdocs/post_mvp.md` — "core / infrastructure" (build order item #7)
**Status:** In progress (Phases 1–2 complete)
**Target phase:** Post-MVP Phase 3 (gating infrastructure)
**Branch:** `feature/celery-and-redis-setup`

---

## Overview

Add Celery + Redis as the project's background task queue. Today every long-running operation (source sync, LLM source-overview generation, use case generation) blocks the request cycle. Celery moves that work onto a worker process; Redis is the broker that mediates between Django and the workers. This unblocks three downstream features (batch table descriptions, scheduled syncs, agentic cross-source discovery) and lets the loading-indicator pattern evolve from "request-blocking spinner" to "fire-and-poll" — eliminating the 30–60s dead-page experience during first sync.

Scope is the infrastructure plus one proof-of-concept conversion (source sync), so we validate the worker + polling pattern end-to-end before downstream features build on it.

---

## Dependencies

- [x] Redis available locally — install via `brew install redis` (Mac) before starting; on Linux the package is `redis-server`. No remote Redis required for dev.
- [x] `apps/sources/views.py` — `sync_source` view exists and currently runs sync work synchronously inside the request. This is the proof-of-concept conversion target.
- [x] `apps/sources/models.py` — `SourceSyncLog` model already tracks sync status (running/success/failed) and timestamps, which is exactly the state the polling indicator will watch.
- [x] HTMX is loaded and the loading-indicator pattern from `devdocs/featuredocs/loading-indicators.md` is in place — Phase 3 of this feature evolves that pattern, doesn't rebuild it.

---

## Out of Scope

- **Batch table description generation** — separate post_mvp item #8. This feature only sets up the queue; #8 builds the fan-out logic on top.
- **Scheduled syncs** — separate post_mvp item #9. This feature lands Celery Beat configuration as foundation, but does not actually wire any source to a schedule.
- **Agentic cross-source discovery** — post_mvp item #10. Multi-step pipeline runs on the queue we set up here but is its own feature.
- **Converting use case generation, source overview, or test connection to tasks** — only sync gets converted as proof-of-concept. Other LLM-bound operations stay synchronous in this feature; conversion happens per-feature when each gets revisited.
- **Production deploy considerations** (managed Redis, supervisor for workers, monitoring) — solo-dev local setup only. Production hardening is a separate concern when deployment is set up.

---

## Implementation Checklist

### Phase 1 — Infrastructure setup ✅

#### Install dependencies

- [x] Added `celery[redis]==5.4.0` to `requirements.txt` (the `[redis]` extra pulls in `redis-py`).
- [x] Added `django-celery-beat==2.9.0` to `requirements.txt`. **Note:** the initial `2.7.0` pin (which the doc had assumed) does not support Django 6.x — `django-celery-beat` requires `>=2.8` for Django 5.x and `>=2.9` for Django 6.x. Lock to whatever pip resolves.
- [x] `pip install -r requirements.txt` succeeds.

#### Local Redis

- [x] Redis installed via `brew install redis` and started as a launchd service (`brew services start redis`).
- [x] `redis-cli ping` returns `PONG`. Default port 6379.

#### Celery app instance

- [x] Create `Flint/celery.py` — defines the Celery app, configures it from Django settings, and enables task auto-discovery across all installed apps. This is the standard Celery + Django 
  boilerplate from the Celery docs (https://docs.celeryq.dev/en/stable/django/first-steps-with-django.html).
- [x] Update `Flint/__init__.py` to import the Celery app so it's available as `Flint.celery_app` whenever Django starts. Standard pattern: `from .celery import app as celery_app; __all__ = ('celery_app',)`.

#### Settings

- [x] In `Flint/settings.py`, add Celery configuration (read from env vars with sensible defaults):
  - `CELERY_BROKER_URL = os.getenv('CELERY_BROKER_URL', 'redis://localhost:6379/0')`
  - `CELERY_RESULT_BACKEND = os.getenv('CELERY_RESULT_BACKEND', 'redis://localhost:6379/1')` (different DB number from broker — keeps results isolated)
  - `CELERY_ACCEPT_CONTENT = ['json']`
  - `CELERY_TASK_SERIALIZER = 'json'`
  - `CELERY_RESULT_SERIALIZER = 'json'`
  - `CELERY_TIMEZONE = TIME_ZONE` (whatever `TIME_ZONE` already is)
  - `CELERY_BEAT_SCHEDULER = 'django_celery_beat.schedulers:DatabaseScheduler'` (uses Django models for schedule storage)
- [x] Add `'django_celery_beat'` to `INSTALLED_APPS`.
- [x] Add the two new env var defaults to `.env.example` (so future setup is documented).
- [x] Also added `CELERY_BROKER_CONNECTION_RETRY_ON_STARTUP = True` to silence the Celery 6.0 pending-deprecation warning by opting into the new default explicitly.

#### Migrations

- [x] Run `python manage.py migrate` to create the `django-celery-beat` tables (PeriodicTask, IntervalSchedule, CrontabSchedule, etc.).

#### First task — verify the worker works

- [x] Created `apps/core/tasks.py` with a trivial `@shared_task def ping() -> str: return 'pong'`.
- [x] Worker starts cleanly (`celery -A Flint worker -l info`) and `apps.core.tasks.ping` appears in the registered `[tasks]` list.
- [x] `ping.delay().get(timeout=5)` returns `'pong'`. Worker logs show `received` then `succeeded in 0.005s` — full pipeline (Django → Redis broker → worker → Redis result backend → caller) verified end-to-end.

### Phase 2 — Dev workflow ✅

#### Daily commands (reference)

Celery runs as its own process — no integration with `manage.py` or `package.json`. Raw commands for fallback / CI / outside-PyCharm use:

- `celery -A Flint worker -l info` — start the worker
- `celery -A Flint beat -l info` — start the scheduler (only needed when periodic tasks are configured; not yet)
- `redis-cli ping` — verify Redis is alive (expects `PONG`)

These are also documented in `CLAUDE.md` "Common Commands".

#### PyCharm run configurations

- [x] `celery worker` config: Python module run, module name `celery`, parameters `-A Flint worker -l info`, project venv interpreter, project root working directory. `PYTHONUNBUFFERED=1` env var (PyCharm default).
- [x] `celery beat` config: same shape, parameters `-A Flint beat -l info`. Created but not yet added to the compound — beat does nothing until scheduled tasks exist (deferred to item #9).
- [x] `Dev Workflow` compound updated: now starts Django + Tailwind watcher + Celery worker in three console tabs. One click brings up everything.
- [x] Worker commands + Redis check documented in `CLAUDE.md` "Common Commands"; Celery configuration notes added to `CLAUDE.md` "Configuration Notes" section.

### Phase 3 — Convert source sync to async (proof of concept)

This validates the polling pattern before downstream features rely on it. Sync is the right candidate because it's the slowest existing operation and the loading-indicators feature already anticipated this conversion.

#### The shape of the change

- [ ] Move the body of `sync_source` (`apps/sources/views.py:155-220`) into a new task `apps/sources/tasks.py::sync_source_task(source_id: int, sync_log_id: int) -> None`. The task does exactly what the view does today — discover catalog, write schemas/tables/columns, generate source overview — but inside the worker process. Pass IDs not model instances (Celery tasks should never serialize Django ORM objects).
- [ ] The view becomes a thin wrapper: create the `SourceSyncLog` row with `status='running'` (so the polling indicator has something to watch), enqueue the task with `sync_source_task.delay(source.pk, sync_log.pk)`, and return immediately.
- [ ] The task updates the same `SourceSyncLog` row to `status='success'` or `status='failed'` when done. No new model needed.

#### Polling indicator template change

- [ ] Add a new `apps/sources/views.py::sync_status` view at `GET /sources/<pk>/sync-status/` that returns the latest `SourceSyncLog` for the source rendered as a small partial (running spinner / success message / error message).
- [ ] Update the Sync Now form in `templates/sources/source_detail.html` to:
  - Continue posting to `sources:sync` on click
  - On response (which now returns immediately because the task is queued, not run inline), HTMX swaps in a polling element via `hx-get="{% url 'sources:sync_status' source.pk %}"` with `hx-trigger="every 2s"` and `hx-swap="outerHTML"` targeting itself.
  - The polling partial has three rendered states: `running` (shows the spinner from `_spinner.html`), `success` (shows a checkmark and `HX-Refresh: true` header to reload the page so all the updated catalog/sync-history sections refresh), `failed` (shows the error message and stops polling by removing the `hx-trigger`).
- [ ] Drop the `HX-Refresh` response from the `sync_source` view itself — the refresh now happens from the polling partial when it sees `success`.

#### Update the loading-indicators featuredoc

- [ ] In `devdocs/featuredocs/loading-indicators.md`, mark the deferred "Celery migration" notes as resolved and link to this featuredoc. The polling pattern is now documented here.

### Phase 4 — Documentation

- [ ] Update `CLAUDE.md` "Common Commands" with the worker command.
- [ ] Add a "Background Tasks" section to `CLAUDE.md` Configuration Notes that names: where the Celery app lives (`Flint/celery.py`), where tasks live (`apps/<app>/tasks.py` per Django convention), and that `redis-cli ping` is the first thing to check when tasks aren't running.
- [ ] Update `devdocs/architecture.md` lines 269–272 to remove the "deferred" framing and replace with a brief note pointing at this featuredoc.

---

## Key Design Decisions

- **Redis as broker AND result backend.** The two roles can be split (RabbitMQ broker + Redis results, or Redis broker + DB results), but for a solo-dev project the operational simplicity of one Redis serving both is worth the trade. We use different DB numbers (0 for broker, 1 for results) so we can wipe one without the other.
- **`shared_task` decorator, not `app.task`.** Tasks declared with `@shared_task` aren't bound to a specific Celery app instance, which means they work whether they're discovered via `Flint.celery_app` or imported directly in tests. The Django+Celery integration docs use this pattern.
- **`django-celery-beat`, not crontab files or static `CELERY_BEAT_SCHEDULE`.** DB-backed periodic tasks let us add/edit/disable schedules from the Django admin without redeploying. Foundation for item #9 (scheduled syncs) where a user might configure cron expressions per source.
- **Pass IDs to tasks, not model instances.** Celery serializes task arguments as JSON. Passing a `Source` object would force pickle serialization and create stale-data risk if the worker ran later than the request. Always pass `source_id: int` and re-query in the task.
- **The polling partial is the indicator, not the form.** Once a sync starts, the form disappears (replaced by the polling partial) so the user can't double-click. When the polling partial reports `success` or `failed`, it swaps back to the form (or triggers a page refresh). This is cleaner than juggling button-disabled state across multiple HTMX requests.
- **Convert only sync in this feature.** Use case generation and source overview are also LLM-blocking, but converting them is a UX decision per feature (do we want them to feel synchronous because they're 5–10s, or async because they're 30s?). Defer those conversions to when each feature gets revisited.

---

## Notes

- **Worker count:** for dev, one worker process with default concurrency (CPU count) is fine. The default `--pool=prefork` works on Mac/Linux. If you see "fork() may break things" warnings on Mac, add `--pool=solo` to the worker command — single-threaded, slow, but predictable.
- **Auto-reload:** Celery doesn't auto-reload on code changes the way `runserver` does. When you edit a task's body, restart the worker. Watching for changes is possible (e.g. `watchdog`) but adds complexity that's not worth it for one-line task edits.
- **Eager mode for tests:** when writing tests for tasks, set `CELERY_TASK_ALWAYS_EAGER = True` in the test settings so tasks run synchronously in-process. No worker needed during testing.
- **Open question — task return values:** for sync, the task doesn't need to return anything (it writes status to `SourceSyncLog`). For future tasks that *do* return useful values, decide between (a) caller polls `result.get()` (simple, but blocks), (b) caller polls a DB row the task writes to (matches our sync pattern, scales). Default to (b) for any user-facing operation.
- **`requirements.txt` doesn't currently exist as a single file** — verify before adding. The project may use `pyproject.toml` or a different dependency-tracking mechanism. Run `ls requirements*` and `cat pyproject.toml 2>/dev/null` first.
- **HTMX `hx-trigger="every 2s"` semantics:** the polling fires every 2 seconds *from the client*. If the worker takes 30 seconds, that's 15 polling requests — each one cheap (single DB read of `SourceSyncLog`). Consider raising the interval to 3–5s after sync conversion is in to reduce load; 2s is fine for the proof-of-concept.
- **Celery + macOS gotcha:** macOS sometimes throws `objc[*]: +[__NSCFConstantString initialize] may have been in progress in another thread...` warnings on worker start. The fix is exporting `OBJC_DISABLE_INITIALIZE_FORK_SAFETY=YES` before starting the worker. Add this to the PyCharm run config's environment variables, or to your shell rc.
- **Production deferred:** when deployment lands, consider Heroku Redis or AWS ElastiCache (managed Redis), and use a process manager (Heroku Procfile entry or systemd unit) for the worker. Out of scope here.