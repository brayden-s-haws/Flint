# Feature: First SaaS Connector Batch via PyAirbyte — HubSpot & Salesforce

**Source:** `devdocs/appdocs/post_mvp.md` — build order item **14** ("First SaaS connector batch via PyAirbyte — HubSpot and Salesforce — `sources`").
**Status:** Not started
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
- [ ] **A HubSpot account + Salesforce account with API credentials** the developer can use for live validation (see Notes — these connectors use OAuth-style creds, more involved than Stripe's single API key).

No new app. No model changes. No new views, URLs, or templates.

---

## Implementation Checklist

Phased by connector so each lands and is validated independently. The two phases are structurally identical (mirror the Stripe seeding done in #13: migrations `0008`/`0010`).

### Phase 1 — HubSpot

#### Spike (confirm config shape)
- [ ] Confirm the `source-hubspot` connector name and its **required config fields** via PyAirbyte's `config_spec` (same approach used for Stripe in #13's Phase 1 spike: `ab.get_source("source-hubspot").config_spec`). Capture the required keys so `config_example` is accurate. **Do not guess the shape** — HubSpot's Airbyte config is OAuth/private-app-token shaped, not a single key (see Notes).

#### Migration / Seeding
- [ ] Data migration (`apps/sources/migrations/0011_*` or next number) seeding the HubSpot `SourceType`, mirroring `0008_seed_stripe_source_type` + `0010_seed_stripe_config_example`:
  - `get_or_create(name='HubSpot', defaults={'airbyte_connector_name': 'source-hubspot'})`
  - set `config_example` to the confirmed HubSpot config skeleton (from the spike)
  - reversible (`delete()` / clear `config_example`), use `apps.get_model` (not a direct import)
  - **Name must be `'HubSpot'`** (proper-cased) — distinct from the existing demo `SourceType` `'HubSpot (Demo)'`, which stays untouched.

#### Validation (end-to-end via UI)
- [ ] Register a **HubSpot** source through the connect form (paste real config JSON), Test Connection, and Sync. Confirm the catalog populates (synthesized `hubspot` schema → HubSpot streams like `contacts`/`companies`/`deals` → typed columns) and the Source Overview insight generates.
- [ ] Confirm sync runs in the Celery worker with `source-hubspot` installed on first use (watch worker logs for the PyAirbyte install step).
- [ ] Confirm intra-source use-case generation works on the HubSpot source.

#### Tests *(deferred to the Phase 6 testing pass #24 — write up in `devdocs/testing.md` under `apps.sources`)*
- [ ] Routing: a HubSpot-backed `SourceType` resolves to `AirbyteConnector` via `build_connector`.

---

### Phase 2 — Salesforce

*(Same structure as Phase 1, for `source-salesforce`.)*

#### Spike (confirm config shape)
- [ ] Confirm the `source-salesforce` connector name and required config fields via `config_spec`. Salesforce's Airbyte config is OAuth-shaped (`client_id`, `client_secret`, `refresh_token`, plus `is_sandbox`/`start_date` options — **confirm, don't assume**; see Notes).

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

- **No new connector code — one migration per source.** This is the entire point of the #13 adapter: `AirbyteConnector` + `build_connector` already serve any Airbyte connector, so HubSpot/Salesforce are added by seeding a `SourceType`, not by writing classes. If either connector turns out to need code changes, that's a signal something in the adapter needs generalizing — flag it rather than special-casing.
- **Seed via data migration, mirroring Stripe.** The established pattern (`0008`/`0009`/`0010`) is `get_or_create(name=..., defaults={'airbyte_connector_name': ...})` + a `config_example` seed, both reversible and using the historical model. Proper display casing (`HubSpot`, `Salesforce`) per the SourceType convention.
- **Config shape comes from `config_spec`, not memory.** Just as Stripe surprised us (it needed `account_id` in addition to the API key), HubSpot and Salesforce configs must be read from each connector's `config_spec` before writing `config_example`. Getting `config_example` right is the main UX deliverable — it's what the user sees in the connect form.
- **`config_example` (static) is the help mechanism, not spec-driven forms.** The fully spec-driven connect form remains the deferred `post_mvp.md` `sources` backlog item; this batch continues to use the static per-type example, and adding HubSpot/Salesforce is exactly the kind of accumulation that will eventually justify that deferred work.
- **Stream-tolerant `test_connection` already handles partial-auth connectors.** If HubSpot or Salesforce `check()` trips on an unauthorized stream (as Stripe's did on the Connect `accounts` stream), the adapter's discovery fallback already reports green when the catalog is discoverable — no per-connector handling needed.

---

## Notes

- **OAuth credential friction is the real work here, not code.** Unlike Stripe (a single `sk_test_...` key), the HubSpot and Salesforce Airbyte connectors are OAuth/token shaped. Typical shapes (⚠️ **confirm via `config_spec` before seeding — these are from memory, not verified**):
  - **HubSpot** — a private-app access token or OAuth: roughly `{"credentials": {"credentials_title": "Private App Credentials", "access_token": "..."}, "start_date": "..."}`.
  - **Salesforce** — OAuth refresh-token flow: roughly `{"client_id": "...", "client_secret": "...", "refresh_token": "...", "is_sandbox": false, "start_date": "..."}`.
  The generic JSON `Textarea` accepts whatever shape; the deliverable is an accurate `config_example` so the user knows what to paste. Obtaining valid credentials (creating a HubSpot private app, a Salesforce connected app + refresh token) is the main friction — budget time for it during validation.
- **First-use connector install latency** applies per connector (PyAirbyte installs `source-hubspot` / `source-salesforce` into isolated venvs on first sync — slow, needs network). Same as Stripe; happens inside the Celery worker, so it doesn't block requests, but the worker environment must permit the install.
- **Migration numbering** — the last `apps/sources` migration is `0010_seed_stripe_config_example`; new migrations start at `0011`.
- **Do not disturb the demo `SourceType`s.** `'HubSpot (Demo)'` (and the other `(Demo)` types) route to `DemoConnector` via `_REGISTRY` and are `is_demo=True` (filtered out of the connect form). The new real `'HubSpot'` type is separate.
- **Open question:** whether to also seed `config_example` values for these in the same migration as the `SourceType` or in a follow-on migration (Stripe split them across `0008` and `0010` only because `config_example` was added later, in `0009`). Since the field now exists, a **single** migration per connector (SourceType + `config_example` together) is cleaner — recommended.
- **Scope guard:** post_mvp lists only HubSpot + Salesforce for #14. Broader SaaS (Google Analytics, Intercom, Shopify, Zendesk, Mixpanel, Amplitude, Segment) is build item **#19**, a separate batch — don't pull it forward here.
