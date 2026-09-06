# Logging Plan

Add logging after the MVP is functionally complete and tested. Focus on the flows that fail silently or involve external systems — auth, tenant resolution, credential encryption, sync operations, and LLM calls.

Use Python's standard `logging` module throughout. No external logging libraries needed for MVP. All loggers should use the `__name__` convention so the module hierarchy is preserved in log output.

> **Scope note (updated 2026-09-03):** the code these sections cover now exists, so each app section below names the concrete file/function to instrument rather than "(when built)". A **Current Logging State** section lists what already logs today (mostly error paths on external calls) so the #25 pass adds the missing INFO/WARNING business events and standardizes the rest rather than duplicating what's there.

---

## Settings Configuration ✅ DONE

> **Done (2026-09-04):** `LOGGING` dict added at the end of `Flint/settings.py` (after the Celery block). Console handler at DEBUG gated by a `require_debug_true` filter (silent in prod); rotating file handler at WARNING → `logs/flint.log` (10 MB × 3 backups). Loggers configured for `django.request` + all six apps (`accounts`, `users`, `sources`, `insights`, `catalog`, `core`), each with `propagate: False`. `logs/` dir committed via `.gitkeep`; `.gitignore` ignores `logs/*.log` and rotated backups. Verified routing: console shows DEBUG+, file catches WARNING+, no double-logging.

~~Add a `LOGGING` dict to `settings.py` (none exists today — this is a clean addition). The structure below is the target state:~~

- ~~**Console handler** for development (DEBUG and above)~~
- ~~**File handler** for production (WARNING and above, rotating)~~
- ~~**Django's request logger** to capture 4xx/5xx automatically~~
- ~~**App-level loggers** for each Django app in `apps/`~~

~~Logger name pattern: `apps.<app_name>` (e.g., `apps.sources`, `apps.insights`)~~

Each module should declare its logger at the top, below imports:
```
logger = logging.getLogger(__name__)
```

Do not use the root logger directly. Always use named loggers.

> **Note on logger names vs. where code lives:** logger names follow `__name__`, so a log line's name reflects the module that emits it, not the app it conceptually belongs to. This matters in two places below: catalog metadata population is emitted from `apps.sources.tasks` (so it logs under `apps.sources`, not `apps.catalog`), and LLM calls are emitted from `apps.insights.tasks` / `apps.insights.cross_source_pipeline` / `apps.insights.services.*`. Configure the `apps.sources` and `apps.insights` loggers accordingly.

---

## What NOT to Log

Never log the following, even at DEBUG level:

- Raw database passwords or connection strings
- Plaintext credentials before encryption
- Full Fernet ciphertext (it's reversible with the key)
- Session tokens or auth cookies
- LLM prompt contents that may contain user data
- LLM response content (may echo source data)
- Airbyte connector config dicts (these *are* the credentials)
- Any field named `password`, `secret`, `token`, or `key`

Log presence/absence and shape, not values. For example: log `"credentials present: True"` not the credentials themselves.

---

## Current Logging State (as of 2026-09-03)

What already emits logs today — the #25 pass should keep/standardize these, not re-add them:

- `apps/sources/tasks.py` — `logger.exception` when `sync_source_task` fails; `logger.warning` in `run_scheduled_sync` for missing source / missing schedule / disabled schedule.
- `apps/sources/views.py` — `logger.warning` when `cron_descriptor` can't describe a crontab (falls back to the stored label).
- `apps/sources/connectors/postgresql.py` — `logger.error` on connection and query failures (returns safe fallback).
- `apps/sources/connectors/airbyte.py` — `logger.error` on `test_connection` / `discover_catalog` failures.
- `apps/insights/tasks.py` — `logger.exception` in every task's `except` (table description, source overview, cross-source, intra-source use cases).
- `apps/insights/cross_source_pipeline.py` — `logger.exception` per skipped hypothesis / use case.
- `demo/connectors/demo_connector.py` — `logger.debug` on connect, `logger.warning` on a missing fixture file.

Everything else below needs a logger added (the module currently has none) or a new call added to an existing logger.

---

## apps.accounts ✅ DONE

> **Done (2026-09-05):** instrumented `middleware.py` (tenant resolve DEBUG / no-membership WARNING / unauthenticated DEBUG), `signals.py` (account creation INFO / invited-user skip DEBUG), and `views.py` (invite sent/accepted INFO, owner-only denials + expired/password-mismatch WARNING — IDs only, never invitee email/token/password). Aside logged for #26: `AccountSettingsView.get_object` guard can `AttributeError` on `request.account is None` (authenticated user with no membership) before the WARNING is reached.

~~**TenantMiddleware** (`apps/accounts/middleware.py` — no logger yet) — `__call__`~~

- ~~DEBUG when `request.account` resolves successfully — include account ID (not name). (High frequency: fires on every authenticated request. Consider DEBUG, not INFO, to avoid noise.)~~
- ~~WARNING when an authenticated user has no `AccountMembership` (the `membership is None` branch) — include user ID; this is the silent state every downstream view depends on.~~
- ~~DEBUG when the request is unauthenticated (expected, high frequency).~~

~~**Account provisioning** (`apps/accounts/signals.py` — no logger yet) — `create_account_for_new_user`~~

- ~~INFO when a new account + owner membership is auto-created on registration — include account ID and owner user ID. (This is the actual creation site; the users-registration INFO below is the request-side counterpart.)~~
- ~~DEBUG when the signal skips creation because `_skip_account_creation` is set (invited user).~~

~~**Invitations** (`apps/accounts/views.py` — no logger yet)~~

- ~~INFO when an invite is sent (`SendInviteView.form_valid`) — include account ID, inviter user ID, invitation ID; never the invitee email.~~
- ~~WARNING on owner-only permission denial (`AccountSettingsView.get_object`, `SendInviteView.dispatch`) — include user ID and account ID.~~
- ~~INFO when an invite is accepted (`accept_invite_view`, POST success path) — include account ID and the new user ID.~~
- ~~WARNING when an invite is rejected: expired (past the 7-day window) or password mismatch — include invitation ID (never the token or password).~~

---

## apps.users

**Registration** (`apps/users/views.py` — no logger yet) — `RegisterUser.form_valid`

- INFO on successful user creation — include user ID (and account ID once the signal has run). Do not log the email address.
- WARNING on registration blocked by the domain guard (`RegistrationForm.clean_email` raising `ValidationError` because an account already exists for the domain) — include the domain, never the full email.

**Login / Logout**

> **Correction:** login and logout use Django's built-in `LoginView` / `LogoutView` (wired in `apps/users/urls.py`), so there is **no custom view function to instrument**. Hook Django's auth signals instead — connect receivers in `apps/users/` (e.g. a `signals.py` registered from `AppConfig.ready()`):
- `user_logged_in` → INFO, include user ID.
- `user_logged_out` → INFO, include user ID.
- `user_login_failed` → WARNING, include the failure (unknown user vs. bad password) if distinguishable; never the submitted password or the raw credentials dict the signal passes.

---

## apps.sources

**Encryption** (`apps/sources/encryption.py` — no logger yet)

- ERROR in `_get_fernet()` when `ENCRYPTION_KEY` is missing (before raising `ImproperlyConfigured`).
- ERROR when `decrypt_credentials` raises (Fernet `InvalidToken`) — log the exception type only.
> **Note:** these functions receive a credentials dict, not a source, so they can't log a source ID. Log the source ID at the **call sites** (`SourceCreateView`/`SourceUpdateView.form_valid`, `test_connection`, `sync_source_task`) where it's in scope; keep the encryption module's own logs payload-free (operation + outcome, never the dict or ciphertext).

**Source create / edit** (`apps/sources/views.py` — has logger)

- INFO on successful create (`SourceCreateView.form_valid`) and edit (`SourceUpdateView.form_valid`) — include source ID, source type, account ID.
- ERROR if credential encryption raises during `form_valid()` — include account ID and exception type.

**Connection test** (`apps/sources/views.py::test_connection` — has logger)

- INFO on success, WARNING on failure — include source ID and source type. (Currently only surfaced to the user via `messages`; add a log line alongside.)

**Manual + scheduled sync** (`apps/sources/tasks.py` — has logger)

- INFO when `sync_source_task` starts — include source ID, sync log ID.
- INFO when it completes — include source ID, sync log ID, `records_synced`, and duration (derive from `SourceSyncLog.started_at`→`completed_at`). Note `records_synced` currently counts **tables**, not rows — say "tables synced" in the message to avoid ambiguity.
- ERROR on failure — **already present** (`logger.exception` at the end of `sync_source_task`); keep it, ensure it includes source ID and sync log ID.
- `run_scheduled_sync` bail-out warnings (no source / no schedule / disabled) — **already present**; keep.

**Schedule lifecycle** (`apps/sources/scheduling.py` — no logger yet)

- INFO on create/update (`create_or_update_source_schedule`), pause (`disable_source_schedule` / `toggle_source_schedule`→paused), resume (`toggle`→enabled), and delete (`delete_source_schedule`) — include source ID and frequency. These mutate the beat `PeriodicTask`, so log the effect for audit.

**Source deletion cleanup** (`apps/sources/signals.py` — no logger yet)

- INFO in `cleanup_insights_on_source_delete` — include source ID, account ID, and the count of insights removed.
- DEBUG in `delete_periodic_task_on_source_delete` — include the periodic task ID removed.

**Connector-level failures** (`apps/sources/connectors/postgresql.py`, `airbyte.py` — both have loggers)

- Connection / discovery / metadata errors are **already logged** at ERROR; keep them and make sure messages don't include the credentials dict (Airbyte's error strings can echo config — scrub or log exception type only).

---

## apps.catalog

**Metadata population** — implemented in `apps/sources/tasks.py::sync_source_task` (there is no separate catalog sync module), so these emit under the `apps.sources` logger, not `apps.catalog`.

- DEBUG per schema/table as the discovery loop runs — include source ID and object name (keep at DEBUG; per-object volume is high).
- INFO on completion of the catalog upsert — include source ID and totals (schemas, tables, columns created/updated). This is the "full metadata sync completed" summary.
- WARNING when a table/column is skipped or a connector returns empty metadata for a table — include source ID, object name, reason.

**Lazy insight trigger** (`apps/catalog/views.py::TableDetailView.get_context_data` — no logger yet)

- DEBUG when a first-view visit creates a pending table-description insight and dispatches the async task — include table ID and insight ID. (Explains the GET-that-writes behavior in the logs.)

---

## apps.insights

**LLM calls** — emitted from `apps/insights/tasks.py` (the four generation tasks), `apps/insights/cross_source_pipeline.py` (the multi-stage pipeline), and the provider layer `apps/insights/services/*`.

- INFO when a generation job starts — include insight ID (or placeholder ID), target type, and provider name. Anchor in each task: `generate_table_description_task`, `generate_source_overview_task`, `generate_intra_source_use_cases_task`, `run_cross_source_discovery_task`.
- INFO when an LLM call completes — include insight ID, provider, model name, and token usage.
> **Note (token usage):** the service methods (`openai_service.py` / `anthropic_service.py`) currently return only the parsed text/JSON and **discard the response object**, so token usage is not available to log yet. To log it, surface `response.usage` from the service layer (e.g. return it alongside the result or log it inside the service). Until then, log provider + model without token counts rather than fabricating them.
- ERROR on failure — **already present** as `logger.exception` in every task and in the pipeline's per-hypothesis/per-use-case handlers; keep, and ensure each includes the insight/placeholder ID.
- Cross-source pipeline (`cross_source_pipeline.py::run_discovery_for_pair`): INFO at start (source pair, account) and at completion (count of use cases stored). The completion count is already logged by `run_cross_source_discovery_task`; avoid double-logging — pick one layer.
> **Note (retries):** the plan's "WARNING on retry" has no anchor yet — there is no retry logic in the tasks or services today. Defer retry logging until a retry mechanism exists (Celery `autoretry_for`, or an explicit loop); if/when added, log attempt number and reason at WARNING.
- Provider selection (`apps/insights/services/provider.py::get_service`): DEBUG on which provider was chosen; ERROR is already raised (not logged) for an unknown provider — add an ERROR log before the `raise`.

Never log prompt text or LLM response content at any level.

---

## Cross-Cutting Concerns

**Multi-tenancy boundary** (`apps/core/mixins.py::TenantQuerysetMixin.get_queryset` — no logger yet)

- WARNING before raising `PermissionDenied` when `request.account` is `None` — include user ID. This should never happen in normal flow, so it's a real signal. (The `raise` already exists; add the log line above it.)

**Unhandled exceptions**

- Django's default 500 handler logs tracebacks automatically — don't duplicate it.
- For HTMX partial views that return an error `HttpResponse(status=400/404/405)` instead of raising (e.g. the guard responses in `apps/insights/views.py` and the `Method not allowed` returns in `apps/sources/views.py`), log WARNING with the context that triggered the degraded response so these non-2xx responses aren't invisible.

**Startup checks** (`AppConfig.ready()`)

- Log an ENCRYPTION_KEY presence check at startup (presence only, never the key). No such check exists today; `apps/sources/apps.py::ready()` currently only imports signals — this is where it would go (or `settings.py` validation).

---

## Log Levels — Quick Reference

| Level | When to use |
|-------|-------------|
| DEBUG | High-frequency internal state, connector loops, ORM query counts |
| INFO | Business events with clear outcomes (user created, sync completed) |
| WARNING | Unexpected but recoverable states (missing account, LLM retry) |
| ERROR | Failures that require attention (encryption failure, sync crash) |
| CRITICAL | Reserved for catastrophic failures (data loss risk, total service outage) |

---

## Notes

- Use `extra={"source_id": ..., "account_id": ...}` on log calls to attach structured context — this makes filtering in log aggregators straightforward later
- Do not use f-strings for log messages — use `%s` style so the string isn't formatted if the log level is disabled
  - Correct: `logger.info("sync complete for source %s", source.id)`
  - Wrong: `logger.info(f"sync complete for source {source.id}")`
- For long-running jobs (sync, LLM calls), log both entry and exit so duration can be derived from timestamps
- When Django moves to production, wire the file handler to a log aggregator (Datadog, Papertrail, etc.) — the `LOGGING` config is already structured for that