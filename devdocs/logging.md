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

## apps.users ✅ DONE

> **Done (2026-09-05):** `views.py::RegisterUser.form_valid` logs INFO on success (user ID + account ID, resolved via `self.object.account_set.first()` since `Account.owner` has no `related_name`; no email). `forms.py::RegistrationForm.clean_email` logs WARNING on the domain-guard block (domain only, never full email). New `apps/users/signals.py` (registered from `UsersConfig.ready()`) hooks the auth signals: `user_logged_in`/`user_logged_out` INFO (logout None-guarded), `user_login_failed` WARNING that logs **nothing** from the `credentials` dict. All receivers type-hinted; `manage.py check` clean.

~~**Registration** (`apps/users/views.py` — no logger yet) — `RegisterUser.form_valid`~~

- ~~INFO on successful user creation — include user ID (and account ID once the signal has run). Do not log the email address.~~
- ~~WARNING on registration blocked by the domain guard (`RegistrationForm.clean_email` raising `ValidationError` because an account already exists for the domain) — include the domain, never the full email.~~

~~**Login / Logout**~~

> ~~**Correction:** login and logout use Django's built-in `LoginView` / `LogoutView` (wired in `apps/users/urls.py`), so there is **no custom view function to instrument**. Hook Django's auth signals instead — connect receivers in `apps/users/` (e.g. a `signals.py` registered from `AppConfig.ready()`):~~
- ~~`user_logged_in` → INFO, include user ID.~~
- ~~`user_logged_out` → INFO, include user ID.~~
- ~~`user_login_failed` → WARNING, include the failure (unknown user vs. bad password) if distinguishable; never the submitted password or the raw credentials dict the signal passes.~~

---

## apps.sources ✅ DONE

> **Progress (2026-09-07):** ✅ all subsections done — Encryption, Source create/edit, Connection test, Manual + scheduled sync, Schedule lifecycle, Source deletion cleanup, and Connector-level failures (verify).

~~**Encryption** (`apps/sources/encryption.py` — no logger yet)~~ ✅ DONE

> **Done (2026-09-06):** `encryption.py` — ERROR in `_get_fernet()` on missing `ENCRYPTION_KEY` (message trimmed to the key case only); ERROR in `decrypt_credentials` on `InvalidToken`, logging exception type only then bare `raise` (behavior unchanged — no call site catches `InvalidToken`). Module stays payload-free; source IDs logged at call sites instead.

- ~~ERROR in `_get_fernet()` when `ENCRYPTION_KEY` is missing (before raising `ImproperlyConfigured`).~~
- ~~ERROR when `decrypt_credentials` raises (Fernet `InvalidToken`) — log the exception type only.~~
> ~~**Note:** these functions receive a credentials dict, not a source, so they can't log a source ID. Log the source ID at the **call sites** (`SourceCreateView`/`SourceUpdateView.form_valid`, `test_connection`, `sync_source_task`) where it's in scope; keep the encryption module's own logs payload-free (operation + outcome, never the dict or ciphertext).~~

~~**Source create / edit** (`apps/sources/views.py` — has logger)~~ ✅ DONE

> **Done (2026-09-06):** `SourceCreateView`/`SourceUpdateView.form_valid` — INFO on create/edit (source ID, source type, account ID); ERROR guard around `encrypt_credentials` logging **account ID** (not source ID — None at create time, before save) + exception type, then re-raise (no dead flash message).

- ~~INFO on successful create (`SourceCreateView.form_valid`) and edit (`SourceUpdateView.form_valid`) — include source ID, source type, account ID.~~
- ~~ERROR if credential encryption raises during `form_valid()` — include account ID and exception type.~~

~~**Connection test** (`apps/sources/views.py::test_connection` — has logger)~~ ✅ DONE

> **Done (2026-09-06):** `test_connection` — INFO on success / WARNING on failure, each logging source ID + source type, alongside the existing `messages`. (405 `Method not allowed` WARNING deferred to the Cross-Cutting Concerns section.)

- ~~INFO on success, WARNING on failure — include source ID and source type. (Currently only surfaced to the user via `messages`; add a log line alongside.)~~

~~**Manual + scheduled sync** (`apps/sources/tasks.py` — has logger)~~ ✅ DONE

> **Done (2026-09-06):** `sync_source_task` — INFO on start (source ID, type, sync log ID) and INFO on completion (source ID, type, sync log ID, `records_synced` worded "tables synced", duration from `started_at`→`completed_at`). Completion log moved out of the `first_synced_at` block so it fires on **every** sync; fixed a latent bug where the old completion line used `len(schema_data.tables)` (dict attr-access `AttributeError` inside the `try` → would mark first syncs failed). Existing ERROR `logger.exception` (source ID + sync log ID) and `run_scheduled_sync` bail-out warnings kept as-is.

- ~~INFO when `sync_source_task` starts — include source ID, sync log ID.~~
- ~~INFO when it completes — include source ID, sync log ID, `records_synced`, and duration (derive from `SourceSyncLog.started_at`→`completed_at`). Note `records_synced` currently counts **tables**, not rows — say "tables synced" in the message to avoid ambiguity.~~
- ~~ERROR on failure — **already present** (`logger.exception` at the end of `sync_source_task`); keep it, ensure it includes source ID and sync log ID.~~
- ~~`run_scheduled_sync` bail-out warnings (no source / no schedule / disabled) — **already present**; keep.~~

~~**Schedule lifecycle** (`apps/sources/scheduling.py` — no logger yet)~~ ✅ DONE

> **Done (2026-09-07):** `scheduling.py` — logger added; INFO on all five mutations (create + update in `create_or_update_source_schedule`, pause in `disable_source_schedule`, pause/resume in `toggle_source_schedule` branched on `was_paused`, delete in `delete_source_schedule`) with source ID + frequency. Toggle logs after `schedule.save()` so the line reflects persisted state.

- ~~INFO on create/update (`create_or_update_source_schedule`), pause (`disable_source_schedule` / `toggle_source_schedule`→paused), resume (`toggle`→enabled), and delete (`delete_source_schedule`) — include source ID and frequency. These mutate the beat `PeriodicTask`, so log the effect for audit.~~

~~**Source deletion cleanup** (`apps/sources/signals.py` — no logger yet)~~ ✅ DONE

> **Done (2026-09-07):** `signals.py` — logger added; INFO in `cleanup_insights_on_source_delete` (source ID, `account_id`, deduped count via `Insight` queryset `.count()` before delete — avoids overcounting from multiple `InsightTarget` rows per insight); DEBUG in `delete_periodic_task_on_source_delete` (periodic task ID + source ID).

- ~~INFO in `cleanup_insights_on_source_delete` — include source ID, account ID, and the count of insights removed.~~
- ~~DEBUG in `delete_periodic_task_on_source_delete` — include the periodic task ID removed.~~

~~**Connector-level failures** (`apps/sources/connectors/postgresql.py`, `airbyte.py` — both have loggers)~~ ✅ DONE (verify — no changes)

> **Verified (2026-09-07):** both connectors already log every ERROR with `type(exc).__name__` only — no credentials dict, no raw exception string (psycopg2/Airbyte messages can echo `host=`/`user=`/config). Nothing to change. (Unrelated typo noted, not fixed: `postgresql.py` "Count not query row counts" → "Could not".)

- ~~Connection / discovery / metadata errors are **already logged** at ERROR; keep them and make sure messages don't include the credentials dict (Airbyte's error strings can echo config — scrub or log exception type only).~~

---

## apps.catalog ✅ DONE

> **Done (2026-09-07):** all points done — emitted under `apps.sources` (metadata) and `apps.catalog` (view) loggers per the naming note.

~~**Metadata population** — implemented in `apps/sources/tasks.py::sync_source_task` (there is no separate catalog sync module), so these emit under the `apps.sources` logger, not `apps.catalog`.~~

> **Done (2026-09-07):** in `sync_source_task`'s discovery loop — DEBUG per schema and per table (source ID + object name). WARNING (no `continue` — purely additive) when a discovered table has **no columns**, chosen over `metadata['row_count'] is None` because Airbyte is schema-only and *always* returns `row_count=None` (that check would spam every Airbyte table); a columnless table is the connector-agnostic "empty metadata" signal. Completion totals: kept the existing completion INFO (tables + duration); schema/column counts deliberately not added.

- ~~DEBUG per schema/table as the discovery loop runs — include source ID and object name (keep at DEBUG; per-object volume is high).~~
- ~~INFO on completion of the catalog upsert — include source ID and totals (schemas, tables, columns created/updated). This is the "full metadata sync completed" summary.~~ *(tables + duration only; schema/column counts skipped by choice)*
- ~~WARNING when a table/column is skipped or a connector returns empty metadata for a table — include source ID, object name, reason.~~

~~**Lazy insight trigger** (`apps/catalog/views.py::TableDetailView.get_context_data` — no logger yet)~~ ✅ DONE

> **Done (2026-09-07):** DEBUG in `TableDetailView.get_context_data`'s first-view block — table ID (`self.object.pk`, not name) + insight ID, after the `generate_table_description_task.delay()` dispatch.

- ~~DEBUG when a first-view visit creates a pending table-description insight and dispatches the async task — include table ID and insight ID. (Explains the GET-that-writes behavior in the logs.)~~

---

## apps.insights ✅ DONE

> **Done (2026-09-07):** LLM logging across `tasks.py`, `cross_source_pipeline.py`, and `services/provider.py`.
> - **Four generation tasks** (`tasks.py`): INFO on start + INFO on completion, each with insight/placeholder ID. Provider **omitted** from messages (always `'anthropic'` today — a constant carries no signal; re-add if a second provider is introduced). Model name + token usage still deferred (service layer discards the response object). Existing `logger.exception` ERRORs kept (intra-source now includes `placeholder_id`). Fixed two bugs introduced mid-pass: a `service`-object repr and a `text.provider` `AttributeError` (would have failed every source overview); both replaced with the omitted-provider approach. Two start logs were also moved above their generation calls.
> - **Provider selection** (`provider.py::get_service`): DEBUG "Selected provider: %s" per branch; ERROR before the unknown-provider `raise`. `api_key` never logged.
> - **Cross-source** (`cross_source_pipeline.py`): start + completion-count INFO live in the **task** layer (`run_cross_source_discovery_task`) only — pipeline `run_discovery_for_pair` adds no start/completion, so no double-logging. Per-hypothesis / per-use-case `logger.exception` handlers kept.
> - **Deliberate exception to "never log LLM content":** `cross_source_pipeline.py` line ~70 logs `hypothesis.get('title')` on a use-case failure. Owner decision (2026-09-07): the title doubles as a system identifier and is treated as harmless non-sensitive LLM output. Intentional and documented — not an oversight; revisit if hypothesis content ever carries source data.
> - Retry WARNING still deferred (no retry mechanism exists).

~~**LLM calls** — emitted from `apps/insights/tasks.py` (the four generation tasks), `apps/insights/cross_source_pipeline.py` (the multi-stage pipeline), and the provider layer `apps/insights/services/*`.~~

- ~~INFO when a generation job starts — include insight ID (or placeholder ID), target type, and provider name. Anchor in each task: `generate_table_description_task`, `generate_source_overview_task`, `generate_intra_source_use_cases_task`, `run_cross_source_discovery_task`.~~
- ~~INFO when an LLM call completes — include insight ID, provider, model name, and token usage.~~ *(provider omitted — constant; model/token deferred)*
> ~~**Note (token usage):** the service methods (`openai_service.py` / `anthropic_service.py`) currently return only the parsed text/JSON and **discard the response object**, so token usage is not available to log yet. To log it, surface `response.usage` from the service layer (e.g. return it alongside the result or log it inside the service). Until then, log provider + model without token counts rather than fabricating them.~~
- ~~ERROR on failure — **already present** as `logger.exception` in every task and in the pipeline's per-hypothesis/per-use-case handlers; keep, and ensure each includes the insight/placeholder ID.~~
- ~~Cross-source pipeline (`cross_source_pipeline.py::run_discovery_for_pair`): INFO at start (source pair, account) and at completion (count of use cases stored). The completion count is already logged by `run_cross_source_discovery_task`; avoid double-logging — pick one layer.~~
> ~~**Note (retries):** the plan's "WARNING on retry" has no anchor yet — there is no retry logic in the tasks or services today. Defer retry logging until a retry mechanism exists (Celery `autoretry_for`, or an explicit loop); if/when added, log attempt number and reason at WARNING.~~ *(still deferred)*
- ~~Provider selection (`apps/insights/services/provider.py::get_service`): DEBUG on which provider was chosen; ERROR is already raised (not logged) for an unknown provider — add an ERROR log before the `raise`.~~

~~Never log prompt text or LLM response content at any level.~~ *(one documented exception — hypothesis title, see note above)*

---

## Cross-Cutting Concerns ✅ DONE

> **Done (2026-09-08):** all three items complete.

~~**Multi-tenancy boundary** (`apps/core/mixins.py::TenantQuerysetMixin.get_queryset` — no logger yet)~~ ✅ DONE

> **Done (2026-09-08):** WARNING with user ID above the existing `PermissionDenied` raise when `request.account is None`. (Unauthenticated `AnonymousUser.id` is `None` — safe, no `AttributeError`; in practice pairs with `LoginRequiredMixin` so it's the authenticated-no-membership case.)

- ~~WARNING before raising `PermissionDenied` when `request.account` is `None` — include user ID. This should never happen in normal flow, so it's a real signal. (The `raise` already exists; add the log line above it.)~~

~~**Unhandled exceptions**~~ ✅ DONE

> **Done (2026-09-08):** **Refactored** the six manual `if request.method != 'POST'` / 405 returns in `apps/sources/views.py` to the `@require_POST` decorator (matching `insights/views.py`) — these now return a proper `HttpResponseNotAllowed` and are **auto-logged at WARNING by `django.request`** (verified via RequestFactory: all six GET→405 with `Allow: POST`, each emitting a `django.request` WARNING). Remaining degraded responses logged manually: the one 404 in `schedule_toggle` (source ID, WARNING) and the ten business-rule 400s in `insights/views.py` — WARNING for "shouldn't happen" states (invalid rating/status, retry-non-failed, pair-with-self, accept/dismiss non-pending-review), INFO for routine rate-limits and preconditions. All log IDs/status enums only, no content.

- ~~Django's default 500 handler logs tracebacks automatically — don't duplicate it.~~
- ~~For HTMX partial views that return an error `HttpResponse(status=400/404/405)` instead of raising (e.g. the guard responses in `apps/insights/views.py` and the `Method not allowed` returns in `apps/sources/views.py`), log WARNING with the context that triggered the degraded response so these non-2xx responses aren't invisible.~~

~~**Startup checks** (`AppConfig.ready()`)~~ ✅ DONE

> **Done (2026-09-08):** `SourcesConfig.ready()` logs an `ENCRYPTION_KEY` presence check — INFO when set, WARNING when missing, **presence only, never the value**. (Runs on every `manage.py` invocation; cheap and presence-only, so fine. Verified: `manage.py check` emits the INFO line.)

- ~~Log an ENCRYPTION_KEY presence check at startup (presence only, never the key). No such check exists today; `apps/sources/apps.py::ready()` currently only imports signals — this is where it would go (or `settings.py` validation).~~

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