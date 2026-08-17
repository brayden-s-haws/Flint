# Feature: First SaaS Connector Batch via PyAirbyte — HubSpot & Salesforce

**Source:** `devdocs/appdocs/post_mvp.md` — build order item **14** ("First SaaS connector batch via PyAirbyte — HubSpot and Salesforce — `sources`").
**Status:** Phase 1 (HubSpot) COMPLETE and Phase 2 (Salesforce) COMPLETE — both validated end-to-end via the Celery worker (catalog, Source Overview insight, use cases); Stripe regression confirmed. Salesforce carries **two documented connector caveats** (refresh-token rotation → single-use tokens; discovery needs `streams_criteria` filtering) — see Notes. Remaining: deferred routing tests (#24) and the follow-ups in the "Follow-ups" note.
**Target phase:** Post-MVP Phase 4 (build order item 14 — the first item after the PyAirbyte adapter #13, which is COMPLETE).
**Suggested branch:** `feature/hubspot-salesforce` — already checked out.

---

## Overview

Register **HubSpot** and **Salesforce** as connectable data sources, routed through the generic `AirbyteConnector` shipped in build item #13. Because the adapter, registry routing, dynamic connect-source form, and metadata-only sync are all already built and connector-agnostic, this batch is expected to be **almost entirely data/config work — no new connector code**: seed a `SourceType` per connector (name + `airbyte_connector_name` + `config_example`) via a data migration, confirm each connector's config shape, and validate each end-to-end through the UI. HubSpot is prioritized first because it matches the existing Sales demo scenario; Salesforce is the most common enterprise CRM.

This is the payoff of #13: adding a maintained SaaS source should now cost one migration + validation, not a new connector class.

---

## Dependencies

Everything here shipped with build item #13 (PyAirbyte adapter) — see `devdocs/featuredocs/airbyte-adapter.md`. This feature only *uses* it.

- [x] **`AirbyteConnector`** — `apps/sources/connectors/airbyte.py`. One generic adapter; `discover_catalog` / `get_table_metadata` / stream-tolerant `test_connection` all work for any Airbyte connector.
- [x] **Registry routing** — `apps/sources/connectors/registry.py::build_connector` routes any `SourceType` whose `airbyte_connector_name` is set to `AirbyteConnector`.
- [x] **`SourceType.airbyte_connector_name` + `SourceType.config_example`** fields (migrations `0006`, `0009`).
- [x] **Dynamic connect-source form** — `SourceForm` renders the JSON-config `Textarea` + `config_example` help for Airbyte-backed types; `SourceCreateView`/`SourceUpdateView` branch credential handling on the SourceType's backing.
- [x] **Sync pipeline + Celery/Redis** — `sync_source_task` consumes the adapter generically; downstream catalog/insights/use-cases are connector-agnostic.
- [x] **Python 3.12 environment with `airbyte==0.53.2` installed** (PyAirbyte has no 3.13 wheels — see the adapter featuredoc).
- [x] **`AIRBYTE_ENABLE_UNSAFE_CODE=true` set process-wide** (web + worker). Required because `source-hubspot` (and likely other custom-code connectors) ships custom Python — PyAirbyte blocks all 
  commands without it. Discovered during the HubSpot spike; see Phase 1 → "Environment" step. Confirm whether `source-salesforce` needs it too during its spike.
- [x] **A HubSpot account + Salesforce account with API credentials** the developer can use for live validation (see Notes — these connectors use OAuth-style creds, more involved than Stripe's 
  single API key).
- [x] **`uv` installed + `AIRBYTE_NO_UV=1` set process-wide** (web + worker). Required because `source-salesforce` can't be pip-installed on Python 3.12 (its `pendulum<3` sdist needs the removed `distutils`); uv builds it cleanly. Discovered during the Salesforce spike — see Phase 2 → "Environment: `uv`". `uv==0.8.24` pinned in `requirements.txt`; flag set in `settings.py`; HubSpot/Stripe regression-checked green.

No new app. No model changes. No new views, URLs, or templates. **Two environment changes** surfaced during the spikes: `AIRBYTE_ENABLE_UNSAFE_CODE=true` (HubSpot — Phase 1) and `uv` + `AIRBYTE_NO_UV=1` (Salesforce — Phase 2).

---

## Implementation Checklist

Phased by connector so each lands and is validated independently. The two phases are structurally identical (mirror the Stripe seeding done in #13: migrations `0008`/`0010`).

### Phase 1 — HubSpot

#### Spike (confirm config shape) — ✅ DONE
- [x] Confirmed `source-hubspot`'s config shape against the installed connector's `config_spec` (`ab.get_source("source-hubspot").config_spec`). **Findings:**
  - **Only `credentials` is required** at the top level. `start_date` is optional but recommended (default is HubSpot's 2006 creation date, which would replicate everything).
  - `credentials` is a `oneOf` with two branches. **The discriminator is `credentials_title` (a `const` string), NOT `auth_type`** — the ⚠️ in Notes was right to be suspicious; the guessed `auth_type: "private_app"` would have failed.
    - **Private App** (simplest for PyAirbyte): requires `access_token` + `credentials_title: "Private App Credentials"`.
    - **OAuth**: requires `client_id` / `client_secret` / `refresh_token` + `credentials_title: "OAuth Credentials"`.
  - ⚠️ **New non-data finding:** `source-hubspot` ships **custom connector code**, so PyAirbyte refuses to run *any* command (`spec`/`check`/`discover`/`read`) unless `AIRBYTE_ENABLE_UNSAFE_CODE=true` is set in the process environment. This is an environment change, not just data/config — see the new "Environment: `AIRBYTE_ENABLE_UNSAFE_CODE`" section below. (Stripe didn't hit this because it's pure declarative YAML.)

#### Environment: `AIRBYTE_ENABLE_UNSAFE_CODE` (do this first — blocks everything)
- [x] Set `AIRBYTE_ENABLE_UNSAFE_CODE=true` **process-wide** so both the web process (Test Connection) and the Celery worker (sync/discover) can run the connector. Recommended home: `os.environ.
setdefault("AIRBYTE_ENABLE_UNSAFE_CODE", "true")` in `Flint/settings.py` (imported by every process), which keeps it out of per-connector code and covers the worker automatically. `.env` alone is **not** sufficient unless the worker's startup also loads it — settings.py is the single point that both processes share.
  - Without this, `test_connection` fails in the web request and `sync_source_task` fails in the worker with `AirbyteConnectorFailedError: Custom connector code is not permitted in this environment`.

#### Migration / Seeding
- [x] Single data migration `apps/sources/migrations/0011_seed_hubspot_source_type.py` seeding the HubSpot `SourceType` + `config_example` together (combined, unlike Stripe's `0008`/`0010` split 
  which only existed because `config_example` was added later in `0009`). Mirror the structure of `0008`/`0010`:
  - `depends on ('sources', '0010_seed_stripe_config_example')`
  - forward: `SourceType.objects.get_or_create(name="HubSpot", defaults={"airbyte_connector_name": "source-hubspot"})`, then set `config_example` (see exact string below) and `.save()`
  - reverse: `SourceType.objects.filter(name="HubSpot").delete()`
  - use `apps.get_model("sources", "SourceType")` (historical model, not a direct import)
  - **Name must be exactly `'HubSpot'`** (proper-cased) — distinct from the existing demo `SourceType` `'HubSpot (Demo)'`, which stays untouched.
  - **Exact `config_example` value** (private-app auth, from the spike — this is the string the connect form shows the user):
    ```json
    {
      "credentials": {
        "credentials_title": "Private App Credentials",
        "access_token": "..."
      },
      "start_date": "2024-01-01T00:00:00Z"
    }
    ```
    As a Python string literal for the migration (mirroring `0010`):
    ```python
    st.config_example = (
        '{\n'
        '  "credentials": {\n'
        '    "credentials_title": "Private App Credentials",\n'
        '    "access_token": "..."\n'
        '  },\n'
        '  "start_date": "2024-01-01T00:00:00Z"\n'
        '}'
    )
    ```

#### Validation (end-to-end via UI) — ✅ DONE
- [x] Registered a **HubSpot** source through the connect form, Test Connection ✅, Sync ✅. Catalog populated (synthesized `hubspot` schema → 36 streams incl. `contacts`/`companies`/`deals` → typed columns), Source Overview insight generated ✅, table descriptions generated ✅.
- [x] Sync ran in the Celery worker ✅.
- [x] Intra-source use-case generation works on the HubSpot source ✅.
- [x] Stripe regression re-tested after the shared-adapter fix — still works ✅.

#### Tests *(deferred to the Phase 6 testing pass #24 — write up in `devdocs/testing.md` under `apps.sources`)*
- [ ] Routing: a HubSpot-backed `SourceType` resolves to `AirbyteConnector` via `build_connector`.

---

### Phase 2 — Salesforce

*(Same structure as Phase 1, for `source-salesforce`.)*

#### Spike (confirm config shape) — ✅ DONE
- [x] Confirmed `source-salesforce`'s config shape against the installed connector's `config_spec`. **Findings:**
  - **Required:** `client_id`, `client_secret`, `refresh_token`.
  - **`auth_type`:** `const: "Client"` — *not* in the required list, but fixed to `"Client"`, so include it in `config_example`.
  - **Optional:** `is_sandbox` (bool), `start_date` (ISO date-time).
  - **Flat config** (no nested `credentials` object — the opposite of HubSpot).
  - **Executor: `VenvExecutor`** (a real Python subprocess connector), *not* `DeclarativeExecutor`. Consequences:
    - The HubSpot `_config_dict` fix **does not apply** (the `getattr`/`hasattr` guard in `AirbyteConnector._get_source` skips it — config flows normally via the `--config` file). ✅ confirmed harmless.
    - Salesforce does **not** need `AIRBYTE_ENABLE_UNSAFE_CODE` (that's a declarative/custom-code concern).
  - ⚠️ **New environment finding:** `source-salesforce` **cannot be installed with pip on Python 3.12.** It pins `airbyte-cdk~=0.59` → `pendulum<3` → `pendulum 2.1.2`, which has no cp312 wheel and whose sdist build imports `distutils` (removed from the 3.12 stdlib, PEP 632). pip's build isolation hides any host `setuptools<74` shim, so the wheel build fails. **Fix: use `uv` instead of pip — verified to build the connector cleanly.** See the new "Environment: `uv`" step below. (2.3.0 is the latest on PyPI; newer Salesforce connectors are Docker/manifest-only, so "pin a newer version" is not an option.)

#### Environment: `uv` (do this first — blocks Salesforce install) — ✅ DONE
- [x] **Installed `uv` and pinned it** in `requirements.txt` (`uv==0.8.24`, grouped with `airbyte`) so the **Celery worker** has it too, not just the local venv.
- [x] **Set `AIRBYTE_NO_UV=1` process-wide** in `Flint/settings.py` (`os.environ.setdefault('AIRBYTE_NO_UV', '1')`, next to `AIRBYTE_ENABLE_UNSAFE_CODE`). Regression-checked: HubSpot + Stripe (both `DeclarativeExecutor`, no venv install) still test green with the flag on, and `uv` has no Python deps, so no conflicts. For reference, the setting mirrors `AIRBYTE_ENABLE_UNSAFE_CODE`:
  ```python
  os.environ.setdefault("AIRBYTE_NO_UV", "1")  # use uv, not pip: pip can't build source-salesforce's pendulum<3 on py3.12
  ```
  ⚠️ **The flag is inverted in PyAirbyte 0.53.2.** `NO_UV = os.getenv("AIRBYTE_NO_UV", "").lower() not in {"1","true","yes"}` (`airbyte/constants.py`), so PyAirbyte *defaults to pip*; setting `AIRBYTE_NO_UV=1` flips `NO_UV` to `False`, which makes it **use uv**. Counter-intuitive, but that's the switch. Both `uv` on PATH **and** this flag are needed — uv on PATH alone does nothing (PyAirbyte still used pip until the flag was set).
  - Without this, `sync_source_task` fails in the worker with `AirbyteConnectorInstallationError` → `Failed building wheel for pendulum` → `ModuleNotFoundError: No module named 'distutils'`.

#### Migration / Seeding — ✅ DONE
- [x] `apps/sources/migrations/0012_seed_salesforce_source_type.py`, mirroring `0011` (get_or_create + `config_example` together):
  - `depends on ('sources', '0011_seed_hubspot_source_type')`
  - forward: `get_or_create(name="Salesforce", defaults={"airbyte_connector_name": "source-salesforce"})`, then set `config_example` via `json.dumps(..., indent=2)` and `.save()`
  - reverse: `SourceType.objects.filter(name="Salesforce").delete()`; `apps.get_model`
  - **Name exactly `"Salesforce"`** (proper-cased per convention).
  - **`config_example`** includes `streams_criteria` (see below) — added *after* validation surfaced the system-object discovery bug (see Notes → "Salesforce discovery fails on system objects"). It filters discovery to the core CRM objects, which both demonstrates the option and steers users past the failure:
    ```json
    {
      "auth_type": "Client",
      "client_id": "...",
      "client_secret": "...",
      "refresh_token": "...",
      "is_sandbox": false,
      "start_date": "2024-01-01T00:00:00Z",
      "streams_criteria": [
        {"criteria": "exacts", "value": "Account"},
        {"criteria": "exacts", "value": "Contact"},
        {"criteria": "exacts", "value": "Opportunity"},
        {"criteria": "exacts", "value": "Lead"}
      ]
    }
    ```

#### Validation (end-to-end via UI) — ✅ DONE (with caveats — see Notes)
- [x] Registered a **Salesforce** source and **Sync succeeded** (12.8s in the Celery worker): catalog populated with the filtered core objects (`Account`/`Contact`/`Opportunity`/`Lead` → typed columns), Source Overview generated. ✅ This validates the full path: uv install → `VenvExecutor` → worker sync → catalog → insight.
- [x] Sync ran in the Celery worker with `source-salesforce` installed via **uv** on first use. ✅
- [x] Use-case generation works on the Salesforce source. ✅
- ⚠️ **Two connector-specific caveats surfaced during validation, both documented in Notes:**
  1. **Refresh-token rotation** (Salesforce's new default) makes tokens single-use → the source works for **one** sync then fails auth. Users must disable rotation on their connected app, or re-mint the token each run. See "Salesforce refresh-token rotation".
  2. **Discovery fails on system objects** without `streams_criteria` filtering (`INVALID_FIELD` on `DataPackageKitDefinition`). The seeded `config_example` now includes a core-object filter. See "Salesforce discovery fails on system objects".
  - Because of rotation, validation was done by minting a fresh token → saving config → **syncing directly, skipping Test Connection** (Test Connection would consume the single-use token before sync).

#### Tests *(deferred to Phase 6 #24)*
- [ ] Routing: a Salesforce-backed `SourceType` resolves to `AirbyteConnector`.

---

## Key Design Decisions

- **No new connector *code* — one migration per source, but each connector has needed a shared environment/adapter accommodation.** The #13 adapter goal holds: `AirbyteConnector` + `build_connector` serve any Airbyte connector, so HubSpot/Salesforce are added by seeding a `SourceType`, not by writing connector classes. But **neither connector was "just a migration"** — the *data* work was trivial; the friction was making PyAirbyte run the connector at all. Every accommodation so far is connector-agnostic (shared env/adapter layer, benefits future connectors), so the "no per-connector classes" principle survives — but budget for one of these per new connector rather than assuming zero:
  1. **HubSpot:** process-wide `AIRBYTE_ENABLE_UNSAFE_CODE=true` (custom-code connectors) + a shared **`AirbyteConnector._get_source` fix** for PyAirbyte's `DeclarativeExecutor` dropping credentials (see Notes → "PyAirbyte DeclarativeExecutor config bug").
  2. **Salesforce:** `uv` + process-wide `AIRBYTE_NO_UV=1` so PyAirbyte builds the connector with uv (pip can't build its `pendulum<3` on py3.12 — see Notes → "Salesforce won't pip-install on Python 3.12").
  - **Takeaway for future SaaS batches (#19):** the spike must include an *install + `check` + `discover` smoke test*, not just `config_spec`. The config shape is the easy part; whether PyAirbyte can execute the connector on this pinned 3.12 environment is where the real work keeps appearing.
- **Seed via data migration, mirroring Stripe.** The established pattern (`0008`/`0009`/`0010`) is `get_or_create(name=..., defaults={'airbyte_connector_name': ...})` + a `config_example` seed, both reversible and using the historical model. Proper display casing (`HubSpot`, `Salesforce`) per the SourceType convention.
- **Config shape comes from `config_spec`, not memory.** Just as Stripe surprised us (it needed `account_id` in addition to the API key), HubSpot and Salesforce configs must be read from each connector's `config_spec` before writing `config_example`. Getting `config_example` right is the main UX deliverable — it's what the user sees in the connect form.
- **`config_example` (static) is the help mechanism, not spec-driven forms.** The fully spec-driven connect form remains the deferred `post_mvp.md` `sources` backlog item; this batch continues to use the static per-type example, and adding HubSpot/Salesforce is exactly the kind of accumulation that will eventually justify that deferred work.
- **Stream-tolerant `test_connection` already handles partial-auth connectors.** If HubSpot or Salesforce `check()` trips on an unauthorized stream (as Stripe's did on the Connect `accounts` stream), the adapter's discovery fallback already reports green when the catalog is discoverable — no per-connector handling needed.

---

## Notes

- **OAuth/token credential friction is the real work here, not code.** Unlike Stripe (a single `sk_test_...` key), these connectors are OAuth/token shaped. Config shapes below are from the **Airbyte connector docs** (the authoritative reference: `docs.airbyte.com/integrations/sources/hubspot` and `/salesforce`) — still cross-check the exact discriminator keys against the installed connector's `config_spec` before finalizing `config_example`, since doc summaries can lag the pinned connector version.
  - **HubSpot** (`source-hubspot`) — ✅ **confirmed via spike.** Nested `credentials` object; only `credentials` is required. The discriminator is **`credentials_title`** (a `const` string), not `auth_type`. Private-app token is simplest for PyAirbyte:
    ```json
    {"credentials": {"credentials_title": "Private App Credentials", "access_token": "..."}, "start_date": "2024-01-01T00:00:00Z"}
    ```
    (OAuth alternative: `credentials` carrying `credentials_title: "OAuth Credentials"` + `client_id`/`client_secret`/`refresh_token`.) ⚠️ Also requires `AIRBYTE_ENABLE_UNSAFE_CODE=true` (custom connector code) — see Phase 1 → "Environment".
  - **Salesforce** (`source-salesforce`) — ✅ **confirmed via spike.** Flat OAuth refresh-token config (no nested object); `client_id`/`client_secret`/`refresh_token` required, `auth_type` is `const: "Client"` (not in `required` but fixed — include it), `is_sandbox`/`start_date` optional:
    ```json
    {"auth_type": "Client", "client_id": "...", "client_secret": "...", "refresh_token": "...", "is_sandbox": false, "start_date": "2024-01-01T00:00:00Z"}
    ```
    ⚠️ Runs as a `VenvExecutor` (real Python connector), so it needs the `uv` install fix (see below), **not** `AIRBYTE_ENABLE_UNSAFE_CODE` or the DeclarativeExecutor adapter fix.
  The generic JSON `Textarea` accepts any shape; the deliverable is an accurate `config_example`. Obtaining valid credentials — a HubSpot **private app**, a Salesforce **connected app** + refresh token — is the main friction; budget time for it during validation.
- **PyAirbyte `DeclarativeExecutor` config bug (custom-components connectors) — required a shared adapter fix.** `source-hubspot` is a low-code connector with **custom Python components**, so PyAirbyte 0.53.2 runs it in-process via `DeclarativeExecutor`. That executor constructs `ConcurrentDeclarativeSource(config=self._config_dict, ...)` where `_config_dict` holds **only the injected component code — not the user's credentials** (`airbyte/_executors/declarative.py`). The current `ConcurrentDeclarativeSource` validates config at construction time, so `check`/`discover`/`read` all fail with `Config validation error: 'credentials' is a required property` **even when the config is correct and valid against the connector spec**. The user config *is* written separately to the `--config` file, but validation happens against the construction config, which lacks it.
  - **Not fixed by upgrading** — the same line exists on PyAirbyte `main` (checked up to 0.55.2); there's no public `set_config` (config is immutable after init).
  - **Fix (shared, in the adapter):** `AirbyteConnector._get_source` merges `self.credentials` into `executor._config_dict` after `ab.get_source(...)`. The `declarative_source` property rebuilds from `_config_dict` on every call, so the merge covers `check`/`discover`/`read`. Guarded with `getattr`/`hasattr` so it's a no-op for connectors without a `DeclarativeExecutor` (e.g. Stripe — regression-tested, still works).
  - ⚠️ **Fragility:** this reaches into a PyAirbyte private attribute (`_config_dict`). If a future PyAirbyte upgrade restructures the executor, the guard degrades it to a silent no-op rather than crashing — but custom-components connectors would break again. Re-verify HubSpot on any PyAirbyte bump. This is the kind of adapter generalization #13's featuredoc anticipated.
  - **Salesforce update:** confirmed NOT affected — `source-salesforce` runs as a `VenvExecutor` (real Python subprocess connector), so the guard skips it and config flows normally via `--config`. This fix is HubSpot-path-only for now.
- **Salesforce won't pip-install on Python 3.12 — use `uv`.** `source-salesforce 2.3.0` (latest on PyPI) pins `airbyte-cdk~=0.59` → `pendulum<3` → `pendulum 2.1.2`. That version has no cp312 wheel, so pip builds it from sdist; its `build.py` does `from distutils.command.build_ext import build_ext`, and **`distutils` was removed from the 3.12 stdlib** (PEP 632). A host `setuptools<74` provides a vendored `distutils`, but pip's build isolation hides it from the build subprocess, so the wheel build fails regardless. **`uv` builds it cleanly** (verified end-to-end: install → `config_spec`). 
  - **Enable uv:** install `uv` (add to requirements so the worker has it) **and** set `AIRBYTE_NO_UV=1` process-wide. Both are needed — uv on PATH alone is ignored.
  - ⚠️ **Inverted flag:** `NO_UV = os.getenv("AIRBYTE_NO_UV","").lower() not in {"1","true","yes"}` (`airbyte/constants.py`). Unset → PyAirbyte uses pip; `AIRBYTE_NO_UV=1` → `NO_UV=False` → uses uv. Yes, `AIRBYTE_NO_UV=1` *enables* uv. Counter-intuitive but correct.
  - Newer Salesforce connector versions (which don't pin `pendulum<3`) are Docker/manifest-only, not on PyPI — so upgrading the connector isn't an option on the venv path; uv is the fix.
- **Salesforce refresh-token rotation → single-use tokens (Flint can't sync repeatedly).** ⚠️ **Confirmed behavior, now Salesforce's default** (even a brand-new Developer Edition org enforces it, alongside required PKCE). Each `grant_type=refresh_token` call returns a **new** refresh token and **immediately invalidates the one just used** — verified directly: call 1 → `200` + a *different* refresh token; call 2 with the same token → `400 invalid_grant`. The connector itself is aware of this (`source_salesforce/api.py` has a `_login_permanently_failed` guard and login dedup with a comment about rotation revoking the whole grant).
  - **Why Flint can't absorb it:** Flint stores credentials once and hands them to PyAirbyte per run; the rotated token lives only inside the connector subprocess and is never returned to Flint, so we can't persist it for the next sync. Rotating refresh tokens are fundamentally incompatible with the stateless-connector model. (HubSpot/Stripe unaffected — different auth.)
  - **Symptom:** first sync succeeds, every subsequent sync (or a Test Connection *followed by* a sync) fails with "The authentication to SalesForce has expired." Test Connection and sync are separate connector invocations, so Test Connection burns the token before sync can use it.
  - **User-facing requirement:** users must **disable refresh-token rotation** on their Salesforce connected app (may require a Salesforce support ticket, like PKCE did) for repeated syncs to work. Without that, only a single sync per freshly-minted token is possible.
  - **Validation workaround used:** minted a fresh token → saved config → **synced directly, skipping Test Connection** (so the sync is the token's first and only use).
  - **OAuth token-minting friction (for the record):** modern SF requires **PKCE** (needs `code_challenge`/`code_verifier` on the auth-code flow) — this org couldn't disable it without contacting support. The manual flow is: browser authorize (with `code_challenge`) → exchange the code (with `code_verifier`) at `/services/oauth2/token`. Gotchas that cost real time: the authorization `code` from the browser is URL-encoded (`%3D`→`=`) and single-use/short-lived; `--data-urlencode` double-encodes an already-encoded code; and the `code_verifier` must match the exact `code_challenge` used in the authorize step.
- **Salesforce discovery fails on system objects without `streams_criteria`.** ⚠️ A full-org discovery describes **every** SObject, and some modern system/Data-Cloud objects have schema mismatches in the connector — e.g. `INVALID_FIELD: No such column 'DataSpaceDefinitionId' on entity 'DataPackageKitDefinition'` — which aborts discovery (exit code 1, empty catalog). Fix: the seeded `config_example` includes a `streams_criteria` filter restricting discovery to core CRM objects (`Account`/`Contact`/`Opportunity`/`Lead`). Filters are **OR-combined** (`source_salesforce/api.py::filter_streams` — matches are appended then de-duped), so each `{"criteria": "exacts", "value": "<SObject>"}` adds one object. Users can widen the list as needed; the default keeps discovery clean out of the box.
- **macOS Celery worker SIGSEGV (fork + PyAirbyte native stack) — fixed via `threads` pool.** ⚠️ After the Airbyte work, PostgreSQL (native) syncs began crashing the worker with `signal 11 (SIGSEGV)` / `WorkerLostError`. Crash report faulting thread: `libdispatch dispatch_apply` → `CoreFoundation CFPreferences` → `Heimdal/Kerberos` (via `libpq`). Cause: Celery's default **prefork** pool forks children; a child that had run an Airbyte sync (loading `pyarrow`/`libarrow` and initializing non-fork-safe Apple frameworks) later ran a Postgres sync, whose `libpq` Kerberos/GSSAPI init touched that fork-tainted GCD/CoreFoundation state → segfault. macOS-only (Linux fork is fine). **Fix:** `settings.py` sets `CELERY_WORKER_POOL = "threads"` when `sys.platform == "darwin"` — no fork, keeps concurrency (all tasks are I/O-bound). Verified: postgres → airbyte → postgres now runs clean; banner shows `concurrency: N (thread)`. See `CLAUDE.md` → Background tasks. (The `OBJC_DISABLE_INITIALIZE_FORK_SAFETY=YES` env var also works but can't be set from Python — too late for the ObjC runtime — so the in-code pool override is preferred.)
- **First-use connector install latency** applies per connector (PyAirbyte installs `source-hubspot` / `source-salesforce` into isolated venvs on first sync — slow, needs network). Same as Stripe; happens inside the Celery worker, so it doesn't block requests, but the worker environment must permit the install (and, for Salesforce, have `uv` + `AIRBYTE_NO_UV=1`).
- **Migration numbering** — `0011_seed_hubspot_source_type` (HubSpot) and `0012_seed_salesforce_source_type` (Salesforce) are both done; next `apps/sources` migration starts at `0013`.
- **Follow-ups (not blocking #14, worth capturing):**
  - **Surface the Salesforce rotation caveat to users in the UI**, not just here — e.g. a note in the connect-form help for the Salesforce type ("disable refresh-token rotation on your connected app, or the source will only sync once"). Right now it's tribal knowledge in this doc.
  - **Consider whether the stateless-connector model needs a token-persistence hook** for any future connector that rotates/expires credentials per use. Salesforce is the first to hit it; #19's broader SaaS batch may surface more. Out of scope for #14.
  - **The `streams_criteria` default is opinionated** (4 core objects). If users expect their full object list by default, revisit — but the discovery-failure protection argues for keeping a sane default filter.
- **Do not disturb the demo `SourceType`s.** `'HubSpot (Demo)'` (and the other `(Demo)` types) route to `DemoConnector` via `_REGISTRY` and are `is_demo=True` (filtered out of the connect form). The new real `'HubSpot'` type is separate.
- **Open question:** whether to also seed `config_example` values for these in the same migration as the `SourceType` or in a follow-on migration (Stripe split them across `0008` and `0010` only because `config_example` was added later, in `0009`). Since the field now exists, a **single** migration per connector (SourceType + `config_example` together) is cleaner — recommended.
- **Scope guard:** post_mvp lists only HubSpot + Salesforce for #14. Broader SaaS (Google Analytics, Intercom, Shopify, Zendesk, Mixpanel, Amplitude, Segment) is build item **#19**, a separate batch — don't pull it forward here.
