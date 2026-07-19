# Feature: PyAirbyte Connector Adapter

**Source:** `devdocs/appdocs/post_mvp.md` — build order item **13** ("PyAirbyte integration — `sources`"). Precursor to item **14** (remaining SaaS connector batch: HubSpot, Salesforce). **Stripe is pulled forward into #13** as the first real Airbyte source, for end-to-end validation against a live dev account.
**Status:** Draft — not started
**Target phase:** Post-MVP Phase 3 (build order item 13 — first item after cross-source discovery #11 and async use-cases #11b, both complete; #12 descoped).
**Suggested branch:** `feature/airbyte-adapter` — already checked out.

---

## Overview

Today every data source Flint syncs goes through a hand-written `BaseConnector` subclass — `PostgreSQLConnector` for real DBs, `DemoConnector` for demo data. Adding a new source means writing a new connector class. This item adds a single **adapter** — `AirbyteConnector(BaseConnector)` — that wraps the [PyAirbyte](https://docs.airbyte.com/using-airbyte/pyairbyte/getting-started) library, so any of Airbyte's 300+ maintained connectors can be registered and synced through the *exact same interface* the rest of the app already uses (`discover_catalog`, `get_table_metadata`, `test_connection`). Catalog, insights, and agentic discovery then work uniformly across native and Airbyte-backed sources with no changes downstream of the connector layer.

The deliverable is the **adapter + the wiring to register and sync an Airbyte source through the UI**, validated end-to-end against a real **Stripe** source (live dev account). Airbyte's credential-free `source-faker` connector is available as a zero-credential smoke test while wiring the library mechanics, but the acceptance bar is a working Stripe sync. The remaining SaaS connectors (HubSpot/Salesforce) stay in item #14; #13 proves the pipe and lands Stripe.

**Airbyte covers databases too, not just SaaS.** Airbyte ships database source connectors — MySQL (`source-mysql`, which also serves MariaDB), Redshift (`source-redshift`), MSSQL, Oracle, MongoDB, etc. — alongside SaaS APIs. Because Airbyte is broad and low-effort to add, the go-forward default is to route **as many new sources as possible through the adapter**, reserving native connectors for cases that need deep introspection (Postgres today).

**The user never sees "native vs Airbyte."** The connect-source flow just lists **supported sources by name** ("PostgreSQL", "Stripe", "MySQL", …); the user picks one and we render the fields that source needs. Native-vs-Airbyte is purely *internal routing* — Postgres renders the structured `host/port/...` form, everything Airbyte-backed renders the JSON-config form — but that distinction is an implementation detail, never surfaced as a category the user has to understand.

The core design challenge is an **impedance mismatch**: `BaseConnector` is database-shaped (schemas → tables → typed columns, plus row counts and column stats), while PyAirbyte is **stream-shaped** (streams with JSON-schema-typed fields, no schema namespace, no row/stat metadata without actually reading records). The adapter's job is the translation, and it should follow the `DemoConnector` precedent (synthesize one schema, return metadata-only stats) to stay faithful to Flint's "inspect metadata, don't store data" principle.

---

## Dependencies

- [ ] **PyAirbyte library** — not yet installed (`pip show airbyte` → not found; no pin in `requirements.txt`). Listed as a planned dep in `architecture.md` (`airbyte  # PyAirbyte`). Needs installing + pinning. Note PyAirbyte itself pulls in a fair dependency tree and manages per-connector installs into isolated venvs on first use.
- [x] **`BaseConnector` interface + registry** — `apps/sources/connectors/base.py` (3 abstract methods), `registry.py` (`_REGISTRY` name→class map + `get_connector`). Reused unchanged in shape; the registry gains Airbyte routing.
- [x] **Sync pipeline is connector-agnostic** — `apps/sources/tasks.py::sync_source_task` already consumes `discover_catalog()` / `get_table_metadata()` generically and upserts into `catalog` models. If the adapter honors the return shapes, **the sync task needs no changes.**
- [x] **`DemoConnector` precedent** — `demo/connectors/demo_connector.py` shows a non-DB `BaseConnector`: single synthesized schema, a `TYPE_MAP` from Python/JSON types to Flint `data_type` strings, and `get_table_metadata` returning `{'row_count': None/len, 'column_stats': {}}`. The Airbyte adapter is structurally the same idea.
- [x] **Fernet credential encryption** — `apps/sources/encryption.py` (`encrypt_credentials` / `decrypt_credentials`) stores a JSON dict in `Source.credentials`. Airbyte config is just a (larger, per-connector-shaped) JSON dict, so this storage works as-is.

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

**Airbyte → Flint mapping the adapter performs:**
- Airbyte **stream** → Flint **table** (`table_type='BASE TABLE'`, matching DemoConnector).
- Stream's JSON-schema `properties` → **columns**; each property's `type`/`airbyte_type` → `data_type` via a `TYPE_MAP`; `nullable` from whether the type union includes `"null"`; `primary_key` from the stream's `source_defined_primary_key`.
- No Airbyte schema namespace → **synthesize one schema** named after the connector/source (DemoConnector returns `[{'name': source, 'tables': [...]}]`).
- `get_table_metadata` → **metadata-only** `{'row_count': None, 'column_stats': {}}` (discovery doesn't read records; see Key Design Decisions).

---

## Implementation Checklist

Multi-phase — this is a larger surface than the recent async conversions. Phases are ordered to de-risk the library first and keep each step independently verifiable.

### Phase 1 — Spike & pin the dependency
- [ ] `pip install airbyte`, pin in `requirements.txt`.
- [ ] **Add a Stripe dev API key to `.env`** (e.g. `STRIPE_API_KEY=sk_test_...`) and document it in `.env.example` — required to run `source-stripe` in the spike and see the real stream shapes. Without it the spike can only use `source-faker`, which won't reveal Stripe's actual catalog.
- [ ] Throwaway spike (shell or `$CLAUDE_JOB_DIR/tmp` script). Start credential-free to prove the mechanics: `import airbyte as ab; s = ab.get_source("source-faker", config={"count": 1000}, install_if_missing=True); s.check(); s.get_available_streams(); s.discovered_catalog`. Then repeat with `source-stripe`, reading the key from `.env` (config likely `{"account_id": ..., "client_secret": "sk_test_...", "start_date": ...}` — confirm from `s.config_spec`) to see the **real target's** stream JSON schemas. Confirm the shapes the mapping depends on: field names, `type`, `airbyte_type`, `source_defined_primary_key`. **De-risk before writing the adapter.**
- [ ] Note the first-run install latency and where PyAirbyte puts connector venvs (affects the Celery worker environment).

### Phase 2 — `AirbyteConnector(BaseConnector)`
- [ ] New `apps/sources/connectors/airbyte.py` — `class AirbyteConnector(BaseConnector)`. `__init__` receives the decrypted credentials dict; it must know **which** Airbyte connector to launch (e.g. `source-faker`) and the connector **config** (see Phase 3 for where the connector *name* comes from).
- [ ] `test_connection()` → wrap `ab_source.check()`; return bool, log + return False on failure (mirror `PostgreSQLConnector.test_connection`'s try/except style).
- [ ] `discover_catalog()` → build the Airbyte source, read `discovered_catalog`, translate each stream → the table dict shape above. Add a `TYPE_MAP` (Airbyte JSON-schema types → Flint `data_type` strings) like DemoConnector's. Return a single synthesized schema.
- [ ] `get_table_metadata()` → return `{'row_count': None, 'column_stats': {}}` (metadata-only). Keep the signature; the stream name is `table_name`.
- [ ] Type hints throughout; `from __future__ import annotations` (project standard).

### Phase 3 — Registry + SourceType routing *(model change)*
- [ ] Add `SourceType.airbyte_connector_name = CharField(null=True, blank=True)` — non-null marks a SourceType as Airbyte-backed and names the connector (`source-stripe`). Migration required. *(Alternative: keep it inside the config JSON; rejected because the connector name is metadata about the type, not a per-source secret.)*
- [ ] **Decouple `SourceType.name` from connector routing.** Today `name` is both the dropdown label *and* the `_REGISTRY` key (`get_connector(source.source_type.name)`), which is why the ad-hoc Postgres row is named lowercase `postgresql` to match `_REGISTRY['postgresql']`. Going forward, `name` is a **display label only** (proper-cased); routing is decided by backing: `airbyte_connector_name` set → `AirbyteConnector` (parameterized by that name); else native `_REGISTRY` lookup. One generic `AirbyteConnector` serves all Airbyte types.
- [ ] **Fix the Postgres casing + seed it properly.** Data migration to rename the existing `'postgresql'` SourceType → `'PostgreSQL'`, update the `_REGISTRY` key to match (`registry.py`, only occurrence — verified via grep), and seed the Postgres SourceType via migration (mirroring `0003_seed_demo_source_types`) so it's consistent across environments instead of hand-created. Proper display casing (`PostgreSQL`, `Stripe`, `MySQL`, `HubSpot`) is the convention for all new SourceTypes.
- [ ] `AirbyteConnector` needs the connector name at construction — plumb it from the `SourceType` (either pass it in, or have the registry hand it to the constructor). Keep `sync_source_task` unchanged if possible; if the constructor signature must change, adjust the two call sites (`tasks.py`, `views.py::test_connection`) consistently.

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
- **Route new sources through Airbyte by default.** Given the adapter's breadth, prefer Airbyte for new sources and reserve native connectors for deep-introspection needs (Postgres). This maximizes coverage for the least per-source effort.
- **Sync pipeline stays untouched.** If the adapter honors the return shapes, `sync_source_task` and the catalog models need no changes — the entire value of conforming to `BaseConnector`.
- **Config stored via existing Fernet encryption.** Airbyte config (often containing API keys/tokens) is just JSON — reuse `encrypt_credentials`; no new secret-storage machinery.

---

## Resolved Decisions

1. **Credential capture UX (Phase 4)** — ✅ **Generic JSON-config textarea.** Spec-driven dynamic forms (from PyAirbyte's `config_spec`) deferred to a later item. The connect form additionally becomes **dynamic**: it swaps between the native structured fields and the JSON textarea based on the selected SourceType's backing.
2. **Where the Airbyte connector name lives (Phase 3)** — ✅ **New `SourceType.airbyte_connector_name` field** (one migration).
3. **Scope line between #13 and #14** — ✅ **Land a real connector (Stripe) inside #13.** Uses the user's live Stripe dev account for end-to-end validation. #14 is reduced to HubSpot + Salesforce.

---

## Notes

- **First-run connector install latency.** PyAirbyte installs each connector into an isolated venv on first use. The first sync of a new Airbyte type will be slow and needs network egress; subsequent runs reuse the install. Because sync already runs in a Celery task, this doesn't block the request — but the worker environment must permit the install. Worth watching in Phase 5.
- **Metadata depth vs. native.** Airbyte discovery is shallower than the Postgres connector (no constraints/indexes/stats). That's expected and documented in `architecture.md`'s "Native vs Airbyte Decision Criteria" — use native when deep introspection matters, Airbyte for breadth. This adapter is the breadth path.
- **`test_connection` cost.** `source.check()` may spin up the connector; it's heavier than a Postgres TCP connect. Fine for a manual button, but note it isn't free.
- **This unblocks #14 and beyond.** #14 (first SaaS batch) and #19/#20 (more SaaS + warehouses) all ride on this adapter. Getting the mapping and registry routing right here pays off repeatedly.
- **No changes to insights/catalog/discovery.** By design, everything past the connector layer is untouched — call that out in the PR so reviewers know the blast radius is `apps/sources` + one migration.
