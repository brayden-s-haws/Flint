# Testing Plan

Write tests now that the MVP is functionally complete. Focus on the flows that would break silently — auth, tenant resolution, form validation, redirects, credential encryption, sync/catalog upserts, and the LLM-backed insight tasks.

Use Django's `TestCase` and `Client` throughout. No external testing libraries needed for MVP.

> **Scope note (updated 2026-09-08):** the code these sections cover now exists, so each section below names the concrete view/model/task/function to test (`file::name`) rather than "(fill in once built)". Every test spec pulled from a `devdocs/featuredocs/*.md` "Tests" section has been folded in here — this document is the single source of truth for the #24 pass; the featuredocs are cross-referenced, not re-read. Build tests app-by-app; every tenant-scoped view and model additionally gets the multi-tenancy boundary test called out in **Cross-Cutting**.

> **Formatting note:** logger names / test anchors follow the module that owns them. Two things emit from a different app than you'd expect (mirrors `logging.md`): catalog metadata population happens in `apps/sources/tasks.py::sync_source_task` (test it under **apps.sources**), and `TableStatistics` creation happens during that same sync (asserted under both **apps.sources** sync tests and **apps.catalog** stats tests).

> **▶ START HERE (#24 execution order):**
> 1. ~~**Test settings first**~~ — ✅ **DONE.** Config wired in `Flint/settings.py` under a `TESTING = 'test' in sys.argv` block (`CELERY_TASK_ALWAYS_EAGER`/`EAGER_PROPAGATES`, `ENCRYPTION_KEY` from `TESTING_ENCRYPTION_KEY`, `ALLOWED_HOSTS=['testserver']`, MD5 password hasher). Two-tenant base `TenantTestCase` lives in `apps/core/test_utils.py`. Also added the missing `apps/__init__.py` (test discovery crashed on the namespace package). Smoke test in `apps/core/tests.py` passes.
> 2. ~~**`apps.core`**~~ — ✅ **DONE.** `apps/core/tests.py` covers base models (`TimeStampedModel`/`TenantAwareModel`), `TenantMiddleware` (all three branches), `TenantQuerysetMixin` (raise + filter), and `DashboardView` (login-required + account-scoped counts). 13 tests passing; module/class docstrings + intent comments added.
> 3. **`apps.users` next** — ⏳ IN PROGRESS. Then **`apps.accounts`** (invitations), **`apps.sources`** (biggest: encryption, sync, connectors, schedules), and finally **`apps.catalog` → `apps.insights`** (which lean on the mock-LLM + eager-Celery patterns).
>
> The app sections below stay in reading order (users→…→core); this note is the execution order.

---

## Test Infrastructure & Conventions

The setup every section below assumes — established once (✅ **DONE**, see step 1 above):

- **Client auth:** use `Client.force_login(user)` to skip the login flow in tests that aren't testing auth itself.
- **Two-tenant fixtures (implemented):** `apps/core/test_utils.py::TenantTestCase` — its `setUpTestData` creates owner user A (`a@acme.com`) and owner user B (`b@other.com`); the `create_account_for_new_user` signal auto-provisions each account, which the base class then fetches as `cls.account_a` / `cls.account_b`. **Distinct email domains** are deliberate so the registration domain-guard never interferes. Subclass this for every tenancy test; each tenant-scoped view/model gets an "A cannot see/act on B" assertion.
- **Mock the LLM everywhere** — patch `apps.insights.services.provider.get_service` (or the specific service methods: `generate_table_description`, `generate_source_overview`, `generate_intra_source_use_case`, and the three cross-source methods) so no network calls fire. Never hit a real provider in tests.
- **Mock the connectors** — patch `psycopg2.connect` (PostgreSQL) and the PyAirbyte source object (`airbyte.get_source`) so connector tests do no network/DB I/O.
- **Celery eager mode (implemented):** `CELERY_TASK_ALWAYS_EAGER = True` (+ `CELERY_TASK_EAGER_PROPAGATES = True`) in the `TESTING` block so `.delay()` runs the task synchronously in-process, no worker/Redis needed (per `celery-and-redis-setup.md`).
- **Test settings (implemented):** config lives in `Flint/settings.py` under a `TESTING = 'test' in sys.argv` block (not a separate settings module, so `python manage.py test` needs no flag). `ENCRYPTION_KEY` is read from the `TESTING_ENCRYPTION_KEY` env var (a valid Fernet key in `.env` / `.env.example`) so credential round-trips work; `ALLOWED_HOSTS` includes `testserver` (the `Client`'s default host); a fast MD5 password hasher speeds up user creation; SQLite as in dev (note: `pg_stats`/pgvector are unavailable, which is why connector metadata is mocked, not run against a real PG). **Discovery fix:** `apps/__init__.py` was added — without it `apps/` was a namespace package and `manage.py test` crashed on `module.__file__` being `None`.
- **Never assert on logged content** — the logging pass (#25) guarantees no credentials/tokens/LLM text are logged; tests should assert behavior/DB state, not log strings.

---

## apps.users

**Registration** (`apps/users/views.py::RegisterUser`, `apps/users/forms.py::RegistrationForm`)
- GET `/auth/register/` returns 200.
- POST with valid data creates a user, **auto-creates an `Account` + owner `AccountMembership`** via the `create_account_for_new_user` signal, logs them in, and redirects to the dashboard.
- POST with mismatched passwords returns 200 with a non-field error.
- POST with duplicate email returns 200 with a field error.
- POST with missing fields returns 200 with field errors.
- **Domain guard** (`RegistrationForm.clean_email`, see `registration-guard-and-invites.md`): a second person whose email domain matches an existing account owner's domain is **blocked** with a `ValidationError` (they must join by invite instead). A free/personal domain in `EXCLUDED_DOMAINS` (e.g. gmail.com) is exempt and always allowed.

**Login** (`apps/users/urls.py` → Django `LoginView` + `apps/users/forms.py::LoginForm`)
- GET `/auth/login/` returns 200.
- POST with valid credentials returns 302 and sets the session.
- POST with a bad password returns 200 with a non-field error.
- POST with an unknown email returns 200 with a non-field error.
- POST with a `next` parameter redirects to `next` after login.

**Logout** (Django `LogoutView`)
- POST `/auth/logout/` clears the session and redirects.

**Auth signals** (`apps/users/signals.py`) — optional/low-priority
- `user_logged_in` / `user_logged_out` / `user_login_failed` receivers are connected and fire on the corresponding events without raising (they log only; `user_login_failed` must never touch the `credentials` dict).

---

## apps.accounts

Account auto-provisioning on registration is covered under **apps.users**. This section covers the invitation lifecycle and owner-only guards.

**Account settings** (`apps/accounts/views.py::AccountSettingsView` — owner-only)
- GET as the account **owner** returns 200; context includes `members`, `pending_invites`, and `invite_form`.
- GET as a **non-owner** member raises `PermissionDenied` (403).
- The view resolves `self.request.account` (not a URL pk) — an authenticated user with no membership is the degenerate case (see Cross-Cutting tenancy guard).

**Send invite** (`apps/accounts/views.py::SendInviteView` — owner-only)
- Owner POST with a valid email creates an `AccountInvitation` (scoped to the account, `invited_by` set) and sends the invite email.
- Non-owner POST raises `PermissionDenied` (403).
- Tenancy: the invitation is created on the inviter's account only.

**Accept invite** (`apps/accounts/views.py::accept_invite_view`)
- GET with a valid, unaccepted token returns 200 and renders the accept form (with the invitee email).
- POST with matching passwords creates the user with `_skip_account_creation=True` (so the registration signal does **not** make a new account), attaches an `AccountMembership` to the **inviting** account with the invited role, logs the user in, and redirects to the dashboard.
- POST past the **7-day** expiry window returns 400.
- POST with mismatched passwords returns 400.
- A missing/already-accepted token returns 404 (`get_object_or_404(..., accepted=False)`).
- **Interplay with the domain guard** (`registration-guard-and-invites.md`): an invited user joins the existing account via this flow instead of being blocked by the registration domain guard.

---

## apps.sources

**Source create / edit + credential encryption** (`apps/sources/views.py::SourceCreateView`/`SourceUpdateView`, `apps/sources/encryption.py`)
- `SourceCreateView`: GET returns 200; POST with valid native-PG fields creates a `Source`, **encrypts** the credentials onto `Source.credentials`, stamps `request.account`, and redirects. Assert the stored `credentials` is ciphertext (not plaintext) and that decrypting round-trips to the submitted dict.
- POST for an Airbyte-backed `SourceType` takes the JSON `config` path (credentials come from the `config` field).
- POST with missing fields re-renders with form errors.
- `SourceUpdateView`: `get_initial` decrypts stored credentials to pre-fill the form; `form_valid` re-encrypts on save. Tenant-scoped (`TenantQuerysetMixin`) — editing account B's source pk returns 404.
- **Encryption unit** (`encryption.py`): `encrypt_credentials`/`decrypt_credentials` round-trip a dict; `decrypt_credentials` on tampered ciphertext raises `InvalidToken`; `_get_fernet` with `ENCRYPTION_KEY` unset raises `ImproperlyConfigured`.

**Source list / detail / delete** (`SourceListView`, `SourceDetailView`, `SourceDeleteView`)
- `SourceListView` returns 200, is account-scoped (`TenantQuerysetMixin`), and filters by `?q=` (name / source-type name) and `?type=` (see `source-list-filtering.md`).
- `SourceDetailView` returns 200, account-scoped; context carries schedule + sync-history state (see the Scheduled-syncs block).
- `SourceDeleteView` is account-scoped; deleting fires the insight-cleanup signal (see the Source-delete block).

**Connection test** (`apps/sources/views.py::test_connection`)
- POST success (mock `connector.test_connection() -> True`) flashes success and redirects; failure (`-> False`) flashes an error.
- `@require_POST`: a GET returns 405.
- Tenancy: another account's source pk returns 404 (`get_object_or_404(..., account=request.account)`).

**Manual sync** (`apps/sources/views.py::sync_source` / `sync_status`, `apps/sources/tasks.py::sync_source_task`)
- `sync_source` POST enqueues `sync_source_task` and returns the sync-status partial for an `HX-Request` (else redirects). `@require_POST` (GET → 405); tenancy (other account → 404).
- `sync_source_task` (eager, mocked connector): decrypts credentials, builds the connector, discovers the catalog, and **upserts** `Schema` / `Table` / `Column` plus a `TableStatistics` snapshot per table. On success marks the `SourceSyncLog` `status='success'`, sets `records_synced` to the **table** count, sets `first_synced_at` on the first-ever sync, and ensures a `source_overview` insight exists + dispatches its generation.
- Failure path: an exception marks the sync log `failed` with `error_message` and does not partially corrupt state (catalog upserts already committed are fine; the log reflects failure).
- `sync_status` (GET poll target, **not** `@require_POST`): returns the status partial while running, and once the latest sync succeeds returns an empty response with `HX-Refresh`. Account-scoped.

**Connectors** (`apps/sources/connectors/`)
- **PostgreSQL** (`postgresql.py`, mock `psycopg2.connect`): `discover_catalog` builds the schema→table→column tree and skips the system schemas (`information_schema`, `pg_catalog`, `pg_toast`); `get_table_metadata` returns `row_count` + `column_stats` in the expected shape; connection/query errors return the safe fallback (empty catalog / `{'row_count': None, 'column_stats': {}}`) rather than raising.
- **Airbyte** (`airbyte.py`, mock the PyAirbyte source — no network; see `airbyte-adapter.md`): `discover_catalog` maps a known stream JSON schema → the expected table/column dicts; `TYPE_MAP` covers the Airbyte JSON-schema types and falls back sanely on unknown types; `get_table_metadata` returns empty stats (schema-only connector).
- **Routing** (`connectors/registry.py::build_connector`, see `airbyte-adapter.md` + `hubspot-salesforce-connectors.md`): a native-PG `SourceType` resolves to `PostgreSQLConnector`; Airbyte-backed types — including HubSpot and Salesforce — resolve to `AirbyteConnector`.

**TableStatistics** (see `table-statistics.md`; created during sync so it also lives under apps.catalog)
- A successful `sync_source_task` creates a `TableStatistics` record linked to each `Table`.
- `PostgreSQLConnector.get_table_metadata` returns `column_stats` as a dict (empty when `pg_stats` has no rows).
- `TableStatistics` model `str`/defaults (null rates, row count) are correct when stats are missing or partial.

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

**Table list / detail** (`apps/catalog/views.py::TableListView`/`TableDetailView` — both `TenantQuerysetMixin`)
- `TableListView` returns 200, is account-scoped (no cross-tenant leakage), and filters by `?q=` (table name) and `?source=` (see `catalog-table-filter.md`).
- `TableDetailView` returns 200, account-scoped; context includes ordered columns and the latest `TableStatistics`.
- **Lazy insight trigger** (`TableDetailView.get_context_data`): the **first** view of a table creates a `pending` `table_description` `Insight` + `InsightTarget` and dispatches `generate_table_description_task`; a **second** view reuses the stored insight and does **not** create a new one or re-dispatch. (Mock the task / use eager mode.)

**Catalog models** (`Schema`, `Table`, `Column`, `TableStatistics`)
- Sync creates `Schema`/`Table`/`Column` rows scoped to the source's account (covered by the sync task test; assert account scoping here).
- `TableStatistics` creation + shape + defaults (see the TableStatistics block under apps.sources — same records, asserted from the catalog side).

---

## apps.insights

Mock the LLM service everywhere (patch `get_service` or the individual methods) and use `CELERY_TASK_ALWAYS_EAGER=True` for task/view tests. Never assert on prompt/response text.

**Insight list / detail** (`InsightListView`/`InsightDetailView` — both `TenantQuerysetMixin`)
- Both return 200 and are account-scoped (account B's insights never appear).
- `InsightListView` filters (see `insight-list-filtering.md`): `?q=` (`text__icontains`), `?type=` (`insight_type`), and `?source=` — a **union**: the source's own insights (`content_type=Source`) **plus** the `table_description` insights for all of that source's tables (`content_type=Table`), so filtering by a source surfaces its whole insight family. All filters compose; results stay account-scoped.

**Table descriptions** (`apps/insights/tasks.py::generate_table_description_task`; views `insight_status`, `insight_retry`; see `async-table-descriptions.md`)
- `generate_table_description_task` (eager, mocked service) sets `insight.text` + `status='active'` on success; on failure sets `status='failed'` (never raises out of the task).
- `insight_status` poll returns the active/pending/failed partial per status; an unrecognized status returns **400**.
- `insight_retry`: re-dispatches for a `failed` insight and resets it to `pending`; a non-`failed` insight returns **400**.
- **Tenancy:** account A cannot poll (`insight_status`) or retry (`insight_retry`) account B's insight (404).

**Source overview** (`generate_source_overview_task`; sync-side handling in `sync_source_task`; see `source-detail-updates.md`)
- `generate_source_overview_task` (eager, mocked) sets `active` on success, `failed` on failure.
- `sync_source_task` overview handling: a **failed** overview insight is deleted and a fresh `pending` one is created + dispatched; an **active** overview insight is left untouched on later syncs.
- Use-cases gate: the generate-use-cases form is hidden while the overview is `pending` or `failed`.
- **Tenancy** on the overview `insight_status` poll (`insight_type='source_overview'` rows).

**Intra-source use cases** (`generate_intra_source_use_cases_task`; views `generate_intra_use_case_suggestions`, `use_cases_status`; see `async-use-cases.md`)
- `generate_intra_source_use_cases_task` (eager, mocked) creates one `active` `use_case_suggestion` `Insight` + `InsightTarget` per returned use case, scoped to the source's account, and **deletes the placeholder** on success.
- Task failure flips the placeholder to `failed` and creates no use-case rows.
- Regeneration is **non-destructive** — a second run appends and never deletes prior `use_case_suggestion` insights.
- `generate_intra_use_case_suggestions` rejects with **400** when no Source Overview exists and when rate-limited (24h); on the happy path it **enqueues** the task (does not call the LLM inline) and returns the use-cases partial.
- **Tenancy:** account A cannot trigger or poll (`use_cases_status`) account B's source use cases (404).

**Rating** (`apps/insights/views.py::rate_insight`)
- Records `approved`/`rejected`; submitting the current rating again toggles back to `none`; any other value returns **400**; account-scoped (B's insight → 404).

**Provider selection** (`apps/insights/services/provider.py::get_service`)
- `get_service('openai')` and `get_service('anthropic')` return the matching `BaseService` wired with the right key; an unknown provider raises `ValueError`.

**Statistics in prompts** (see `table-statistics.md`)
- The prompt/context builder includes the most recent `TableStatistics.column_stats` when a recent record exists.
- Stats older than 7 days are **excluded** from prompt injection (stale stats are misleading).

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

## apps.core

**TenantMiddleware** (`apps/accounts/middleware.py::TenantMiddleware` — tenancy machinery; grouped here with the other cross-app tenancy tests)
- Authenticated user **with** a membership → `request.account` is set to that account.
- Authenticated user **without** a membership → `request.account is None`.
- Unauthenticated request → `request.account is None`.

**TenantQuerysetMixin** (`apps/core/mixins.py::TenantQuerysetMixin.get_queryset`)
- Raises `PermissionDenied` when `request.account is None`.
- Otherwise filters `super().get_queryset()` to `account=request.account` (the tenancy backbone the boundary tests exercise per-view).

**Dashboard** (`apps/core/views.py::DashboardView`)
- `LoginRequiredMixin`: unauthenticated → redirect to login.
- Counts (sources, tables, insights, `cross_source_insight_count`) are account-scoped — account B's rows never inflate account A's dashboard.

**Base models** (`apps/core/models.py::TimeStampedModel`, `TenantAwareModel`)
- `TimeStampedModel` sets `created_at`/`updated_at`; `updated_at` advances on save.
- `TenantAwareModel` requires an `account` (tenant-scoped models can't be saved without one).

---

## Cross-Cutting

**Multi-tenancy boundary (required for every tenant-scoped view/model)**
- For each detail/edit/delete/action view, account A acting on account B's object returns **404** (`get_object_or_404(..., account=request.account)` or `TenantQuerysetMixin`), except owner-only account views which return **403** (`PermissionDenied`).
- For each list view (`SourceListView`, `TableListView`, `InsightListView`, `CrossSourceDiscoveryView`) and the dashboard counts, account B's rows never appear in account A's results.

**Auth required**
- Every `@login_required` / `LoginRequiredMixin` view redirects an unauthenticated request to the login URL.

**Degraded HTTP responses** (mirrors the #25 logging pass)
- The six `@require_POST` source views (`test_connection`, `sync_source`, `schedule_create`, `schedule_toggle`, `schedule_delete`, `load_demo_data`) return **405** on a GET. (Django logs these via `django.request`; the tests just assert the status.)
- The business-rule guards return their documented status (400/404) — covered in each view's section above.

---


## Notes

- Use `Client.force_login()` to skip auth setup in tests that aren't testing auth itself.
- Mock external calls (LLM APIs, database connectors) with `unittest.mock.patch` — patch at the seam (`get_service`, `psycopg2.connect`, `airbyte.get_source`), never hit the network.
- Set `CELERY_TASK_ALWAYS_EAGER = True` in test settings so `.delay()` runs tasks synchronously in-process (no worker/Redis).
- Test multi-tenancy boundaries: a user from account A should never see or act on account B's data — this is the single most important invariant, and every tenant-scoped app needs it.
- Keep a valid `ENCRYPTION_KEY` and `testserver` in `ALLOWED_HOSTS` in test settings.
