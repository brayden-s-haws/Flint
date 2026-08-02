# Feature: PyAirbyte Connector Adapter

**Source:** `devdocs/appdocs/post_mvp.md` — build order item **13** ("PyAirbyte integration — `sources`"). Precursor to item **14** (remaining SaaS connector batch: HubSpot, Salesforce). **Stripe is pulled forward into #13** as the first real Airbyte source, for end-to-end validation against a live dev account.
**Status:** Phases 1–3 complete — spike + dependency (Python 3.12), `AirbyteConnector` (verified against live Stripe), and registry/`SourceType` routing (`airbyte_connector_name` field, `build_connector` factory, Postgres casing fixed). Phase 4 (dynamic connect-source form + seed the Stripe SourceType) is next. See **Phase 1 Spike — Findings** below.
**Target phase:** Post-MVP Phase 3 (build order item 13 — first item after cross-source discovery #11 and async use-cases #11b, both complete; #12 descoped).
**Suggested branch:** `feature/airbyte-adapter` — already checked out.

---

## Overview

Today every data source Flint syncs goes through a hand-written `BaseConnector` subclass — `PostgreSQLConnector` for real DBs, `DemoConnector` for demo data. Adding a new source means writing a new connector class. This item adds a single **adapter** — `AirbyteConnector(BaseConnector)` — that wraps the [PyAirbyte](https://docs.airbyte.com/using-airbyte/pyairbyte/getting-started) library, so any of Airbyte's 300+ maintained connectors can be registered and synced through the *exact same interface* the rest of the app already uses (`discover_catalog`, `get_table_metadata`, `test_connection`). Catalog, insights, and agentic discovery then work uniformly across native and Airbyte-backed sources with no changes downstream of the connector layer.

The deliverable is the **adapter + the wiring to register and sync an Airbyte source through the UI**, validated end-to-end against a real **Stripe** source (live dev account). Airbyte's credential-free `source-faker` connector is available as a zero-credential smoke test while wiring the library mechanics, but the acceptance bar is a working Stripe sync. The remaining SaaS connectors (HubSpot/Salesforce) stay in item #14; #13 proves the pipe and lands Stripe.

**Airbyte covers databases too, not just SaaS.** Airbyte ships database source connectors — MySQL (`source-mysql`, which also serves MariaDB), Redshift (`source-redshift`), MSSQL, Oracle, MongoDB, etc. — alongside SaaS APIs, so the adapter *can* back a database source (it's the fallback path for one). **But the go-forward policy is that databases/warehouses default to a *native* connector, not Airbyte** — they expose stats catalogs (row counts, column stats, FK constraints) that only a native connector can read, and Airbyte discovery is schema-only. Airbyte is the default for SaaS/APIs and the fallback for low-priority/long-tail database engines. See `architecture.md` → "Native vs Airbyte Decision Criteria" (decided 2026-08).

**The user never sees "native vs Airbyte."** The connect-source flow just lists **supported sources by name** ("PostgreSQL", "Stripe", "MySQL", …); the user picks one and we render the fields that source needs. Native-vs-Airbyte is purely *internal routing* — Postgres renders the structured `host/port/...` form, everything Airbyte-backed renders the JSON-config form — but that distinction is an implementation detail, never surfaced as a category the user has to understand.

The core design challenge is an **impedance mismatch**: `BaseConnector` is database-shaped (schemas → tables → typed columns, plus row counts and column stats), while PyAirbyte is **stream-shaped** (streams with JSON-schema-typed fields, no schema namespace, no row/stat metadata without actually reading records). The adapter's job is the translation, and it should follow the `DemoConnector` precedent (synthesize one schema, return metadata-only stats) to stay faithful to Flint's "inspect metadata, don't store data" principle.

---

## Dependencies

- [x] **PyAirbyte library** — installed and pinned: `airbyte==0.53.2` in `requirements.txt` (new "Connectors / data sources" section). **Requires Python 3.12** (see the Python 3.12 finding below). Pulls a large transitive tree (pyarrow 21, pandas, grpc, cryptography, etc.) and installs each connector into an isolated venv on first use (via `uv`); first-run install adds latency + needs network egress, and PyAirbyte writes connector logs under `/tmp/airbyte/logs/` — both relevant to the Celery worker environment in Phase 5.
- [x] **`BaseConnector` interface + registry** — `apps/sources/connectors/base.py` (3 abstract methods), `registry.py` (`_REGISTRY` name→class map + `get_connector`). Reused unchanged in shape; the registry gains Airbyte routing.
- [x] **Sync pipeline is connector-agnostic** — `apps/sources/tasks.py::sync_source_task` already consumes `discover_catalog()` / `get_table_metadata()` generically and upserts into `catalog` models. If the adapter honors the return shapes, **the sync task needs no changes.**
- [x] **`DemoConnector` precedent** — `demo/connectors/demo_connector.py` shows a non-DB `BaseConnector`: single synthesized schema, a `TYPE_MAP` from Python/JSON types to Flint `data_type` strings, and `get_table_metadata` returning `{'row_count': None/len, 'column_stats': {}}`. The Airbyte adapter is structurally the same idea.
- [x] **Fernet credential encryption** — `apps/sources/encryption.py` (`encrypt_credentials` / `decrypt_credentials`) stores a JSON dict in `Source.credentials`. Airbyte config is just a (larger, per-connector-shaped) JSON dict, so this storage works as-is.

---

## Phase 1 Spike — Findings (2026-07-26)

Validated live against `source-faker` (credential-free) **and** `source-stripe` (real dev account). Everything the Phase 2 mapping depends on is now confirmed against real data.

### Environment — the project moved to Python 3.12
- **PyAirbyte does not install on Python 3.13.** Latest `airbyte` (0.53.2) pins `pyarrow<18`, and pyarrow only ships 3.13 wheels from v18+, so pip falls back to a source build that fails. Worse, even when PyAirbyte itself is force-installed on 3.13 (via a `uv --override pyarrow>=18`), the **connectors** build into their own venvs on the same interpreter and their deps (e.g. `pendulum` for `source-faker`) have no 3.13 wheels either. `source-faker` is the simplest connector Airbyte ships and it already fails on 3.13. **The `--no-deps`/override family of hacks does not work — it produces a PyAirbyte that imports but can't run a single connector.**
- **On Python 3.12 everything installs from wheels, no hacks.** `pip install airbyte` → 0.53.2 + pyarrow 21; `source-faker` and `source-stripe` both install and run.
- **Action taken:** the project `.venv` was rebuilt on Python 3.12.0; `requirements.txt` migrate + Django system check pass clean. `3.13` references updated in `CLAUDE.md`, `README.md`, and `devdocs/getting_started.md`. **Do not "upgrade" the project to 3.13 until PyAirbyte supports it** — it will silently re-break connector installs.

### `check()` semantics (matters for `test_connection`)
- PyAirbyte's `source.check()` **returns `None` on success and raises on failure** (`AirbyteConnectorCheckFailedError`). So `test_connection()` **cannot** `return source.check()` — it must `try: source.check(); return True except Exception: return False` (matches the mirror-`PostgreSQLConnector` guidance in Phase 2).

### Known issue — Stripe `check()` fails on the Connect `accounts` stream *(deferred)*
- `source-stripe` requires **two** config fields, both `required`: `client_secret` (the `sk_test_...` key) **and** `account_id` (`acct_...`). `start_date` is optional. `account_id` is fetchable from `GET /v1/account` with the key.
- On a plain test account, `check()` **fails with a 401 on the `accounts` stream** (Stripe Connect's connected-accounts endpoint) even though the key is valid and every other stream works. Two fixes, **not yet applied** (user deferred): (a) enable Stripe Connect in the test dashboard so `/v1/accounts` returns 200; and/or (b) make the adapter's `test_connection()` **tolerant** — don't fail the whole check because one of 47 streams is unauthorized (arguably the more correct design; a user's key legitimately may not cover every stream). Revisit in Phase 5. **Discovery is unaffected** — `discovered_catalog` returns static schemas without needing every stream to authorize, so Phase 1 completed despite this.
- *(Spike-only, not an adapter concern: the throwaway script's manual `GET /v1/account` call hit `CERTIFICATE_VERIFY_FAILED` because the python.org macOS Python has no system CA store — fixed with `ssl.create_default_context(cafile=certifi.where())`. The connector itself bundles certifi and is unaffected.)*

### Confirmed Airbyte→Flint mapping (from real Stripe + faker catalogs)
- **`stream.name`** → Flint table name. `source-stripe` discovered **47 streams** (`customers`, `charges`, `invoices`, `payment_intents`, …), some wide — `invoices` has **90 columns**.
- **`stream.source_defined_primary_key`** is a **list of lists**, e.g. `[['id']]` → flatten to a set of PK column names, set `primary_key=True` on matches.
- **`json_schema['properties']`** → columns. Each property's `type` is **usually a nullable union**, e.g. `['null', 'string']`, `['null', 'integer']`, `['null', 'object']`, `['null', 'array']`, `['null', 'number']`. So the adapter must:
  - derive **`nullable`** = `'null' in type_list`;
  - take the **real type** = the non-`'null'` element;
  - **handle both forms** — `type` can be a plain `str` (faker had some) *or* a `list`.
- **`TYPE_MAP` keys actually observed:** `string`, `integer`, `number`, `boolean`, `object`, `array` (map `object`/`array` → a JSON-ish Flint type). Include a sane fallback for unknowns.
- **`airbyte_type` is an optional refinement, not the primary signal.** Stripe returned `airbyte_type=None` on every field; faker returned `airbyte_type='timestamp_with_timezone'` on its `created_at`. **Prefer `airbyte_type` when present, else fall back to the union `type`.** (Testing both connectors is what surfaced this — Stripe alone would have hidden it.)
- **Stripe quirk (faithful, not a bug):** timestamps like `created`/`updated` come through as **`integer`** (Unix epoch), so they map to an integer type, not a date.

### Throwaway spike script
The spike lived at `$SCRATCHPAD/stripe_spike.py` (session-scratch, not committed). Reproducible from the notes above if needed again.

---

## The `BaseConnector` contract the adapter must satisfy

Exact shapes the sync task depends on (from `PostgreSQLConnector` / `DemoConnector`):

```python
discover_catalog() -> list[dict]
# [ {'name': <schema>, 'tables': [
#     {'name': <table>, 'table_type': <str>, 'columns': [
#         {'name': <col>, 'data_type': <str>, 'nullable': <bool>, 'primary_key': <bool>}
#     ]}
# ]} ]

get_table_metadata(schema_name: str, table_name: str) -> dict
# {'row_count': int | None, 'column_stats': {<col>: {'null_fraction', 'distinct_count', 'common_values'}} }

test_connection() -> bool
```

**Airbyte → Flint mapping the adapter performs** *(confirmed against real catalogs — see Phase 1 Spike Findings for the exact shapes):*
- Airbyte **stream** → Flint **table** (`table_type='BASE TABLE'`, matching DemoConnector).
- Stream's JSON-schema `properties` → **columns**; `data_type` via `TYPE_MAP` preferring `airbyte_type` when present, else the union `type`; `nullable` = `'null'` in the (list-or-str) `type`; `primary_key` from `source_defined_primary_key` (a **list of lists**, flatten it).
- No Airbyte schema namespace → **synthesize one schema** named after the connector/source (DemoConnector returns `[{'name': source, 'tables': [...]}]`).
- `get_table_metadata` → **metadata-only** `{'row_count': None, 'column_stats': {}}` (discovery doesn't read records; see Key Design Decisions).

---

## Implementation Checklist

Multi-phase — this is a larger surface than the recent async conversions. Phases are ordered to de-risk the library first and keep each step independently verifiable.

### Phase 1 — Spike & pin the dependency — ✅ COMPLETE (2026-07-26)
- [x] `pip install airbyte`, pin in `requirements.txt` → `airbyte==0.53.2`. **Required moving the project to Python 3.12** (3.13 is incompatible — see Findings).
- [x] **Added `STRIPE_API_KEY` to `.env`** and documented it in `.env.example` (new "Source Connector Credentials" section). Confirmed `source-stripe` also needs `account_id` (`acct_...`), fetchable from `GET /v1/account`.
- [x] Throwaway spike run against **both** `source-faker` (mechanics) and `source-stripe` (real target). Confirmed the shapes the mapping depends on — field names, `type`, `airbyte_type`, `source_defined_primary_key` — all captured in **Phase 1 Spike — Findings** above.
- [x] Noted first-run install latency + logs at `/tmp/airbyte/logs/`; connectors install into isolated venvs via `uv` (Celery-env implication flagged for Phase 5).

### Phase 2 — `AirbyteConnector(BaseConnector)` — ✅ COMPLETE (2026-08-02)
Implemented in `apps/sources/connectors/airbyte.py`; verified end-to-end against live Stripe via a throwaway script (`AirbyteConnector(config, "source-stripe").discover_catalog()` → 1 synthesized `stripe` schema, 47 tables, `id` PK, correct type mapping; `get_table_metadata` metadata-only; `test_connection()` returns `False` gracefully on the deferred Connect 401).
- [x] `AirbyteConnector(BaseConnector)` with a **two-arg `__init__(credentials, connector_name)`** (the connector name is passed in, not read from credentials) and a private `_get_source()` helper wrapping `ab.get_source(name, config=credentials, install_if_missing=True)`.
- [x] `test_connection()` → try/except around `source.check()`, returns `True`/`False` (respects the `check()`-returns-`None`/raises finding). **Connect-tolerance deferred to Phase 5** — currently returns `False` for the non-Connect Stripe account.
- [x] `discover_catalog()` → translates `discovered_catalog.streams` → one synthesized schema of tables/typed columns. `TYPE_MAP` (11 keys, full Airbyte vocabulary) + `_resolve_data_type` (airbyte_type → union-`type` → `format` refinement, per the CDK's own resolution order) + `_is_nullable` (nullable-union) + list-of-lists PK flatten. Logs + returns `[]` on failure.
- [x] `get_table_metadata()` → `{'row_count': None, 'column_stats': {}}` (metadata-only).
- [x] Type hints throughout; `from __future__ import annotations`.

### Phase 3 — Registry + SourceType routing *(model change)* — ✅ COMPLETE (2026-08-02)
Migrations `0006` (field) + `0007` (Postgres rename) applied cleanly; existing Postgres sources confirmed renamed to `PostgreSQL`. `build_connector` routing verified in the shell: `PostgreSQL → PostgreSQLConnector`, `HubSpot (Demo) → DemoConnector`, an Airbyte-backed type → `AirbyteConnector`.
- [x] Added `SourceType.airbyte_connector_name = CharField(max_length=255, blank=True)` — non-empty marks a SourceType as Airbyte-backed; native types leave it `''` (routing uses a truthy check). Migration `0006`.
- [x] **Decoupled `SourceType.name` from routing** — `name` is now display-only; routing decided by backing (`airbyte_connector_name` set → `AirbyteConnector`; else native `_REGISTRY` lookup).
- [x] **Fixed Postgres casing + seeding** — data migration `0007_update_postgres_casing` renames `'postgresql'` → `'PostgreSQL'` in place (falls back to `get_or_create`), reversible; `_REGISTRY` key updated to `'PostgreSQL'`.
- [x] **Added `build_connector(source_type, credentials) -> BaseConnector` to `registry.py`** — returns a built instance; lazy `from .airbyte import AirbyteConnector` for the Airbyte branch, native `get_connector(source_type.name)(credentials)` otherwise. `source_type` hinted via a `TYPE_CHECKING` import.
- [x] Updated both call sites (`tasks.py`, `views.py`) to `build_connector(source.source_type, credentials)`; `sync_source_task`'s body otherwise unchanged.

### Phase 4 — Dynamic connect-source form + register an Airbyte source *(credential capture generalization — the biggest UX surface)*
- [ ] **Make the connect-source form dynamic: the user picks a supported source by name, and we render the fields that source needs.** The native-vs-Airbyte split stays *invisible* — no category toggle, just a flat list of SourceTypes by display name. `SourceForm` is currently hardcoded to Postgres fields. On selection: a **native** type (Postgres) renders the structured `host/port/dbname/user/password` fields; an **Airbyte-backed** type (`airbyte_connector_name` set) renders a single **JSON config `Textarea`**. Recommended interaction: select the SourceType, then swap the field set via **HTMX** (`hx-get` a partial keyed on the chosen type) — or a two-step page (pick type → form).
- [ ] JSON textarea is validated as parseable JSON, then encrypted via `encrypt_credentials` exactly like Postgres creds. Defer spec-driven dynamic forms (from PyAirbyte's `config_spec`) to a later item.
- [ ] `SourceCreateView.form_valid` / `SourceUpdateView` build the credentials dict from the JSON config for Airbyte types (branch on the SourceType's backing) instead of the fixed host/port/... dict.
- [ ] Styled widgets on any new form field per `CLAUDE.md` (Tailwind input classes + `__init__` `attrs.update`); the `Textarea` gets the same input classes.
- [ ] Seed the **Stripe** SourceType (`airbyte_connector_name='source-stripe'`) via a data migration mirroring `0003_seed_demo_source_types`. Optionally also seed `source-faker` for credential-free testing.

### Phase 5 — End-to-end validation via Stripe
- [ ] Register a **Stripe** source through the UI (dev-account API key in the JSON config), run a manual sync, confirm the catalog populates (synthesized schema → Stripe stream-tables like `charges`, `customers`, `invoices` → typed columns) and the existing Source Overview insight generates as usual (proves the whole pipe works unchanged past the connector).
- [ ] `test_connection` view works for the Stripe source (green/red as today, via `source.check()`).
- [ ] Confirm the sync runs inside the Celery worker with `source-stripe` installed on first use (watch worker logs for the PyAirbyte install step).
- [ ] *(Optional)* repeat the smoke test with `source-faker` to confirm the adapter is genuinely connector-agnostic and not accidentally Stripe-specific.

### Tests *(deferred to the Phase 6 testing pass #24 — write up in `devdocs/testing.md` under `apps.sources`)*
- [ ] `AirbyteConnector.discover_catalog` maps a known stream JSON schema → the expected table/column dicts (mock the PyAirbyte source object; no network).
- [ ] `TYPE_MAP` covers the Airbyte JSON-schema types and falls back sanely on unknown types.
- [ ] `get_connector` routes an Airbyte-backed SourceType to `AirbyteConnector` and native types to their existing classes.
- [ ] Tenancy unchanged: Airbyte sources are still account-scoped through `Source`/sync like every other source.

---

## Key Design Decisions

- **One generic adapter, not one class per source.** Unlike native connectors (a class per DB), all Airbyte connectors share `AirbyteConnector`, parameterized by the Airbyte connector name stored on `SourceType`. This is the whole point of item #13 — 300+ sources without 300 classes.
- **Metadata-only `get_table_metadata` (no data pull).** Airbyte discovery yields stream *schema*, not row counts or column stats — those require actually reading records, which Airbyte streams into a cache. Reading data contradicts Flint's "inspect metadata, don't store the data" principle and adds cost/latency. Return `{'row_count': None, 'column_stats': {}}` like `DemoConnector`. *(Future option, flagged not built: pull a small sample to estimate stats for LLM context — a deliberate, separate decision.)*
- **Synthesize a single schema.** Airbyte has no schema namespace; emit one schema named after the source/connector so the existing schema→table→column catalog hierarchy is satisfied (DemoConnector does exactly this).
- **Validate with a real Stripe source (dev account).** The user has a live Stripe dev account, so #13 lands one real connector end-to-end rather than only synthetic data. `source-faker` remains a useful zero-credential smoke test for the library mechanics, but the acceptance bar is Stripe. Stripe therefore moves out of #14's batch; #14 becomes HubSpot + Salesforce.
- **The connect-source form is driven by native-vs-Airbyte, but the user never sees that distinction.** The user picks a supported source by name; the SourceType's backing (`airbyte_connector_name` set or not) silently decides which field set renders. No "database vs SaaS" category is surfaced — Airbyte covers databases too, so that split would misroute an Airbyte database (MySQL) to the native form anyway.
- **`SourceType.name` is a display label, not a routing key.** Historically `name` doubled as the `_REGISTRY` lookup key, which forced the ad-hoc Postgres row to lowercase `postgresql`. This feature decouples them: `name` is proper-cased display text; routing goes through `airbyte_connector_name` (Airbyte) or the native registry. Proper display casing is the convention for every new SourceType.
- **Route new *SaaS/API* sources through Airbyte by default; databases/warehouses default to native.** Given the adapter's breadth, prefer Airbyte for SaaS/API sources — it maximizes coverage for the least per-source effort. **But databases and data warehouses default to a native connector:** they expose their own stats catalogs (row counts, column stats, FK constraints) that only a native connector can read, and those feed insights + the queries app. Airbyte stays an acceptable **fallback** for low-priority/long-tail database engines. Full rationale + criteria live in `architecture.md` → "Native vs Airbyte Decision Criteria" (decided 2026-08).
- **Sync pipeline stays untouched.** If the adapter honors the return shapes, `sync_source_task` and the catalog models need no changes — the entire value of conforming to `BaseConnector`.
- **Config stored via existing Fernet encryption.** Airbyte config (often containing API keys/tokens) is just JSON — reuse `encrypt_credentials`; no new secret-storage machinery.

---

## Resolved Decisions

1. **Credential capture UX (Phase 4)** — ✅ **Generic JSON-config textarea.** Spec-driven dynamic forms (from PyAirbyte's `config_spec`) deferred to a later item. The connect form additionally becomes **dynamic**: it swaps between the native structured fields and the JSON textarea based on the selected SourceType's backing.
2. **Where the Airbyte connector name lives (Phase 3)** — ✅ **New `SourceType.airbyte_connector_name` field** (one migration).
3. **Scope line between #13 and #14** — ✅ **Land a real connector (Stripe) inside #13.** Uses the user's live Stripe dev account for end-to-end validation. #14 is reduced to HubSpot + Salesforce.

---

## Notes

- **Python 3.12 is now required (was 3.13).** PyAirbyte + its connectors have no Python 3.13 wheels; the project `.venv` was rebuilt on 3.12.0 during the Phase 1 spike and the `3.13` references in `CLAUDE.md` / `README.md` / `devdocs/getting_started.md` were updated. Don't bump back to 3.13 until PyAirbyte supports it. Full rationale in **Phase 1 Spike — Findings**.
- **First-run connector install latency.** PyAirbyte installs each connector into an isolated venv on first use. The first sync of a new Airbyte type will be slow and needs network egress; subsequent runs reuse the install. Because sync already runs in a Celery task, this doesn't block the request — but the worker environment must permit the install. Worth watching in Phase 5.
- **Metadata depth vs. native.** Airbyte discovery is shallower than the Postgres connector (no constraints/indexes/stats). That's expected and documented in `architecture.md`'s "Native vs Airbyte Decision Criteria" — use native when deep introspection matters, Airbyte for breadth. This adapter is the breadth path.
- **`test_connection` cost.** `source.check()` may spin up the connector; it's heavier than a Postgres TCP connect. Fine for a manual button, but note it isn't free.
- **This unblocks #14 and beyond.** #14 (first SaaS batch) and #19/#20 (more SaaS + warehouses) all ride on this adapter. Getting the mapping and registry routing right here pays off repeatedly.
- **No changes to insights/catalog/discovery.** By design, everything past the connector layer is untouched — call that out in the PR so reviewers know the blast radius is `apps/sources` + one migration.
