# Feature: Intra-Source Suggested Use Cases + Demo Mode (Phase 1)

**Source:** `devdocs/appdocs/post_mvp.md` — "sources — Intra-Source Suggested Use Cases" and "Demo Mode"
**Status:** Not started
**Target phase:** Post-MVP Phase 2

---

## Overview

On the source detail page, add a **"Suggested Uses"** section that surfaces 4–6 LLM-generated analytical use cases derived from the tables within that source. Each card includes a plain-English description and a starter SQL query. This gives users immediate, actionable intelligence from their connected data without any cross-source complexity.

To make this feature demonstrable without requiring the user to connect a real non-PostgreSQL source, we'll also build **Demo Mode Phase 1**: a `DemoConnector` backed by local JSON files that implements the same `BaseConnector` interface as the PostgreSQL connector. This gives us multiple realistic sources (HubSpot, Google Analytics, Customer DB) to showcase use case generation on, without building real SaaS connectors.

---

## Dependencies

- [x] `apps/insights/` — `Insight`, `InsightTarget`, LLM provider abstraction, prompt system all in place
- [x] `apps/sources/` — `Source`, `SourceType`, `SourceSyncLog` in place; `source_detail.html` exists
- [x] `apps/catalog/` — `Schema`, `Table`, `Column` models in place; sync populates them
- [x] Source Overview insight must exist for a source before use case generation is triggered (it provides LLM context)
- [ ] `Insight` model needs a `JSONField` (`structured_data`) for storing structured use case output without parsing JSON from a text field

---

## Implementation Checklist

### Phase A — Demo Mode (Phase 1)

Build this first so use case generation can be tested on interesting multi-table sources without connecting a real database.

#### Model Change
- [ ] Add `is_demo` boolean field (default `False`) to `SourceType` model
- [ ] Run `makemigrations` and `migrate`

#### Demo Data Files
- [ ] Create `demo/data/sales/` directory with JSON files for the Sales scenario:
  - `hubspot_contacts.json` — ~50 rows: `email`, `first_name`, `last_name`, `lifecycle_stage`, `lead_score`, `last_activity_date`, `company_id`
  - `hubspot_companies.json` — ~20 rows: `company_id`, `name`, `industry`, `employee_count`, `annual_revenue`, `country`
  - `hubspot_deals.json` — ~30 rows: `deal_id`, `company_id`, `contact_id`, `stage`, `amount`, `close_date`, `owner`
  - `ga_sessions.json` — ~100 rows: `session_id`, `user_email`, `date`, `source`, `medium`, `campaign`, `pages_viewed`, `session_duration_sec`, `converted`
  - `ga_page_events.json` — ~100 rows: `session_id`, `page_path`, `time_on_page_sec`, `scroll_depth_pct`
  - `ga_goal_completions.json` — ~30 rows: `session_id`, `user_email`, `goal_name`, `completed_at`
  - `customerdb_customers.json` — ~50 rows: `customer_id`, `email`, `company_name`, `plan_tier`, `mrr`, `subscription_start_date`, `renewal_date`
  - `customerdb_feature_usage.json` — ~100 rows: `customer_id`, `feature_name`, `usage_count`, `last_used_date`
  - `customerdb_invoices.json` — ~60 rows: `invoice_id`, `customer_id`, `amount`, `status`, `due_date`
- [ ] Data must have intentional overlap: `contacts.email` ↔ `ga_sessions.user_email` ↔ `customerdb_customers.email`; include edge cases (contacts with no GA sessions, customers with no deals)
- [ ] Dates must be recent (within last 90 days) and internally consistent

#### Demo Connector
- [ ] Create `demo/connectors/demo_connector.py` — `DemoConnector` implementing `BaseConnector` interface:
  - `test_connection() -> bool` — always returns `True`
  - `discover_catalog() -> list[Schema]` — reads JSON files, returns schema/table/column structure
  - `get_table_metadata(table) -> TableMetadata` — returns column metadata from JSON structure
- [ ] Register `DemoConnector` in the connector registry — route to it when `source_type.is_demo is True`

#### Demo Source Types & Seeding
- [ ] Add three demo `SourceType` records (via data migration or management command): `HubSpot (Demo)`, `Google Analytics (Demo)`, `Customer Database (Demo)` — all with `is_demo=True`

#### UI Entry Point
- [ ] Add a "Load Demo Data" button/link on the dashboard empty state (when no sources are connected)
- [ ] Create a `load_demo_data` view in `apps/sources/views.py` — `POST /sources/demo/load/`:
  - Creates three `Source` records (one per demo source type) linked to the current account
  - Triggers sync for each (calls sync logic, populates catalog from JSON)
  - Redirects to dashboard
- [ ] Add URL for `load_demo_data` view in `apps/sources/urls.py`
- [ ] Show a "Demo Data" banner on source cards/detail pages when `source.source_type.is_demo is True`
- [ ] Add a "Clear Demo Data" button on each demo source detail page — deletes demo sources and their associated catalog/insight records

---

### Phase B — `Insight` Model: `structured_data` Field

- [ ] Add `structured_data = models.JSONField(null=True, blank=True)` to `Insight` model
- [ ] Run `makemigrations` and `migrate`
- [ ] No changes needed to existing insight flows — field is optional and null by default

---

### Phase C — Use Case Generation (Core Feature)

#### Prompt
- [ ] Create `apps/insights/prompts/use_case_suggestions.py`:
  - System message instructing the LLM to act as a senior data analyst
  - `build_use_case_suggestions_prompt(source: Source) -> str` — builds DDL-style table/column summary from `Schema`/`Table`/`Column` models, appends existing Source Overview insight text as context, asks for 4–6 distinct use cases with starter SQL
  - Model constant and max tokens constant (use `anthropic`)
  - Structured output JSON format matching:
    ```json
    {
      "use_cases": [
        {
          "title": "...",
          "description": "...",
          "tables": ["TableA", "TableB"],
          "starter_sql": "SELECT ..."
        }
      ]
    }
    ```

#### Service
- [ ] Add `generate_use_case_suggestions(source: Source) -> list[dict]` to `BaseService` (`services/base.py`)
- [ ] Implement in `services/anthropic_service.py` — calls LLM with structured JSON output, parses and returns list of use case dicts
- [ ] Implement stub in `services/openai_service.py` (or full implementation — match anthropic)

#### Storage
- [ ] In the generation view, for each use case dict returned by the service:
  - Create one `Insight` record with `insight_type='use_case_suggestion'`, `status='complete'`, `text=use_case['title']`, `structured_data=use_case` (full dict)
  - Create one `InsightTarget` linking the `Insight` to the `Source` via `GenericForeignKey`

#### View
- [ ] Add `GenerateUseCaseSuggestionsView` to `apps/insights/views.py` — `POST /insights/use-cases/generate/<source_id>/`:
  - Checks that a Source Overview insight exists for the source; if not, return an error response prompting the user to generate one first
  - Checks rate limit: if `use_case_suggestion` insights exist for this source and the most recent was created within the last 24 hours, return an error response
  - Deletes existing `use_case_suggestion` insights for this source (and their `InsightTarget` records)
  - Calls `generate_use_case_suggestions(source)`
  - Stores results as `Insight` + `InsightTarget` records
  - Returns HTMX partial re-rendering the Suggested Uses section
- [ ] Add URL in `apps/insights/urls.py`: `POST /insights/use-cases/generate/<int:source_id>/`

#### Template
- [ ] Add **Suggested Uses** section to `sources/source_detail.html`, below the Source Overview card:
  - **Empty state** (no use cases yet): prompt text + "Generate Suggestions" button that POSTs to `GenerateUseCaseSuggestionsView` via HTMX
  - **Loaded state** (use cases exist): grid of use case cards, each showing:
    - Title (bold)
    - Description (2–3 sentences)
    - Table badges row (`Customer`, `Invoice`, etc.)
    - Collapsible `<details>`/`<summary>` code block with starter SQL
  - **Regenerate** button (visible when cards are shown) — same POST target as Generate, disabled if rate-limited (show "Available in X hours" message)
  - HTMX target the Suggested Uses section so generation replaces the section in place without full page reload

---

## Key Design Decisions

- **`structured_data` JSONField over parsing text:** The use case JSON (title, description, tables, sql) is stored in `Insight.structured_data` so the template can access fields directly without parsing. The `text` field stores just the title as a human-readable label.
- **`insight_type='use_case_suggestion'`:** Follows the existing pattern for insight types; allows filtering use case insights from table descriptions and source overviews without a new model.
- **Source Overview as prerequisite:** The LLM is given the Source Overview as context so it understands what the source is before generating use cases. Gate generation behind Source Overview existence.
- **Rate limit (24 hours):** Checked in the view by querying the `created_at` of existing `use_case_suggestion` insights. No external scheduler needed.
- **Starter SQL is display-only:** Never executed. When the `queries` app is built, these become seed queries. Do not add any SQL execution infrastructure here.
- **Demo connector is permanent:** The `DemoConnector` is never replaced by real connectors — it coexists. Real HubSpot/GA connectors will have their own `SourceType` records; demo variants keep `is_demo=True`.
- **Demo data is intentionally designed for cross-source overlap:** `email` is the shared join key across all three sales scenario sources. This makes the use cases more interesting (they reference cross-table joins) even though the use case generation feature itself is single-source.

---

## Notes

- When building `build_use_case_suggestions_prompt()`, use the same DDL reconstruction pattern as `build_source_overview_prompt()` — query `Schema → Table → Column` for the source and format as `CREATE TABLE` statements.
- The collapsible SQL block in the template should use native HTML `<details>`/`<summary>` — no JS needed. Style the `<code>` block inside with a monospace font and dark background matching the rest of the UI.
- Demo JSON data should be generated carefully: overlap keys (`email`, `company_id`) must appear in multiple sources with matching values, not just structurally similar column names. A few rows should intentionally have no match across sources to make insights about gaps possible.
- Open question: should the "Load Demo Data" action also auto-generate Source Overview insights immediately after sync, so the user can go straight to use case generation? Post-MVP doc says Phase 2 handles auto-trigger — leave it manual for now, but note this as a natural Phase 2 follow-on.