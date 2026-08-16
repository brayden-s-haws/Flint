# Feature: First SaaS Connector Batch via PyAirbyte — HubSpot & Salesforce

**Source:** `devdocs/appdocs/post_mvp.md` — build order item **14** ("First SaaS connector batch via PyAirbyte — HubSpot and Salesforce — `sources`").
**Status:** Phase 1 (HubSpot) COMPLETE — validated end-to-end in the UI (Test Connection, Celery sync, catalog, Source Overview insight, table descriptions, intra-source use cases). Stripe regression confirmed. Phase 2 (Salesforce) not started.
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

No new app. No model changes. No new views, URLs, or templates. **One environment change** (`AIRBYTE_ENABLE_UNSAFE_CODE=true`) surfaced during the HubSpot spike — see Phase 1.

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

#### Spike (confirm config shape)
- [ ] Confirm `source-salesforce`'s config shape from the **Airbyte connector docs** (`docs.airbyte.com/integrations/sources/salesforce`) and cross-check against `config_spec`. Flat OAuth config: `client_id`/`client_secret`/`refresh_token` (required), `auth_type: "Client"`, `is_sandbox`/`start_date` (optional) — see Notes.

#### Migration / Seeding
- [ ] Data migration seeding the Salesforce `SourceType` (`get_or_create(name='Salesforce', defaults={'airbyte_connector_name': 'source-salesforce'})`) + `config_example` from the spike; reversible; `apps.get_model`.

#### Validation (end-to-end via UI)
- [ ] Register a **Salesforce** source through the connect form, Test Connection, Sync; confirm the catalog populates (Salesforce streams like `Account`/`Contact`/`Opportunity` → typed columns) and Source Overview generates.
- [ ] Confirm sync runs in the Celery worker with `source-salesforce` installed on first use.
- [ ] Confirm use-case generation works on the Salesforce source.

#### Tests *(deferred to Phase 6 #24)*
- [ ] Routing: a Salesforce-backed `SourceType` resolves to `AirbyteConnector`.

---

## Key Design Decisions

- **No new connector code — one migration per source (plus a shared env var + one shared adapter fix).** This is the point of the #13 adapter: `AirbyteConnector` + `build_connector` serve any Airbyte connector, so HubSpot/Salesforce are added by seeding a `SourceType`, not by writing connector classes. HubSpot surfaced **two** shared-layer changes (both connector-agnostic, both benefiting all future custom-components connectors — so the "no per-connector classes" principle still holds):
  1. Process-wide `AIRBYTE_ENABLE_UNSAFE_CODE=true` (custom-code connectors) — a shared environment setting.
  2. A shared **`AirbyteConnector._get_source` fix** for how PyAirbyte's `DeclarativeExecutor` handles custom-components connectors (see Notes → "PyAirbyte DeclarativeExecutor config bug"). This generalizes the adapter — it's not HubSpot special-casing.
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
  - **Salesforce** (`source-salesforce`) — flat OAuth refresh-token config; `client_id`/`client_secret`/`refresh_token` required, `is_sandbox`/`start_date` optional:
    ```json
    {"auth_type": "Client", "client_id": "...", "client_secret": "...", "refresh_token": "...", "is_sandbox": false, "start_date": "2024-01-01T00:00:00Z"}
    ```
  The generic JSON `Textarea` accepts any shape; the deliverable is an accurate `config_example`. Obtaining valid credentials — a HubSpot **private app**, a Salesforce **connected app** + refresh token — is the main friction; budget time for it during validation.
- **PyAirbyte `DeclarativeExecutor` config bug (custom-components connectors) — required a shared adapter fix.** `source-hubspot` is a low-code connector with **custom Python components**, so PyAirbyte 0.53.2 runs it in-process via `DeclarativeExecutor`. That executor constructs `ConcurrentDeclarativeSource(config=self._config_dict, ...)` where `_config_dict` holds **only the injected component code — not the user's credentials** (`airbyte/_executors/declarative.py`). The current `ConcurrentDeclarativeSource` validates config at construction time, so `check`/`discover`/`read` all fail with `Config validation error: 'credentials' is a required property` **even when the config is correct and valid against the connector spec**. The user config *is* written separately to the `--config` file, but validation happens against the construction config, which lacks it.
  - **Not fixed by upgrading** — the same line exists on PyAirbyte `main` (checked up to 0.55.2); there's no public `set_config` (config is immutable after init).
  - **Fix (shared, in the adapter):** `AirbyteConnector._get_source` merges `self.credentials` into `executor._config_dict` after `ab.get_source(...)`. The `declarative_source` property rebuilds from `_config_dict` on every call, so the merge covers `check`/`discover`/`read`. Guarded with `getattr`/`hasattr` so it's a no-op for connectors without a `DeclarativeExecutor` (e.g. Stripe — regression-tested, still works).
  - ⚠️ **Fragility:** this reaches into a PyAirbyte private attribute (`_config_dict`). If a future PyAirbyte upgrade restructures the executor, the guard degrades it to a silent no-op rather than crashing — but custom-components connectors would break again. Re-verify HubSpot on any PyAirbyte bump. This is the kind of adapter generalization #13's featuredoc anticipated.
  - **Salesforce implication:** if `source-salesforce` is also a custom-components connector, this same fix already covers it — but confirm during its spike (it may run as a pure-Python subprocess executor instead, in which case the guard just skips).
- **First-use connector install latency** applies per connector (PyAirbyte installs `source-hubspot` / `source-salesforce` into isolated venvs on first sync — slow, needs network). Same as Stripe; happens inside the Celery worker, so it doesn't block requests, but the worker environment must permit the install.
- **Migration numbering** — the last `apps/sources` migration is `0010_seed_stripe_config_example`; new migrations start at `0011`.
- **Do not disturb the demo `SourceType`s.** `'HubSpot (Demo)'` (and the other `(Demo)` types) route to `DemoConnector` via `_REGISTRY` and are `is_demo=True` (filtered out of the connect form). The new real `'HubSpot'` type is separate.
- **Open question:** whether to also seed `config_example` values for these in the same migration as the `SourceType` or in a follow-on migration (Stripe split them across `0008` and `0010` only because `config_example` was added later, in `0009`). Since the field now exists, a **single** migration per connector (SourceType + `config_example` together) is cleaner — recommended.
- **Scope guard:** post_mvp lists only HubSpot + Salesforce for #14. Broader SaaS (Google Analytics, Intercom, Shopify, Zendesk, Mixpanel, Amplitude, Segment) is build item **#19**, a separate batch — don't pull it forward here.
