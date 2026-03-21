# Post-MVP: Deferred Features

Concrete features that are out of scope for the MVP but will need to be built. Organized by app.

For speculative or longer-horizon ideas, see `devdocs/potential_features.md`.

---

## accounts

- **Account settings page** — allow the account owner to rename their account (`/account/settings/`)
- **Domain-based registration guard** — public registration remains open, but during sign-up check whether the user's email domain is already associated with an existing account; if so, block 
  registration and show a message: "An account already exists for this domain — contact your administrator to request access" (do not expose the owner's identity); if no account exists for the 
  domain, registration proceeds normally and a new account is created; existing owners provision additional users from their domain via the team invites flow (exclude common domains like 
  gmail.com, yahoo.com, outlook.com)
- **Team invites** — account owner provisions a new user by email and assigns a role; the `AccountInvitation` model (planned, see `devdocs/architecture.md`) tracks pending invites; invited user receives an email with a tokenised link to set their password and activate their account (similar to Django's password reset flow using `PasswordResetForm` machinery)
- **Multi-account switching** — users can belong to more than one account; UI to switch context
- **Role-based permissions** — expand beyond `owner` only; add `admin`, `member`, `viewer` roles to `AccountMembership`; `admin` can invite/provision users, `member` has read-write access, `viewer` is read-only

---

## catalog

- **TableStatistics** — snapshot-based stats (row counts, column null rates, etc.); model planned but not built for MVP
- **Schema filter on table list** — filter table list by source or schema (UI enhancement)

---

## insights

- **InsightBuilder** — cross-source exploration sessions; model planned (`InsightBuilder`) but deferred
- **Cross-source insights** — insights that span multiple sources or tables
- **Batch insight generation** — generate descriptions for all tables in a source at once (requires Celery)
- **Insight approval/rating** — thumbs up/down workflow so users can accept or reject generated insights

---

## insights — Agentic Cross-Source Discovery

### Overview

The MVP insight generator is **user-initiated and single-source**: the user clicks "Generate Description" on a table and gets back an LLM-written description of that table. The `InsightBuilder` (already deferred) extends this to user-initiated cross-source exploration — the user says "I have Salesforce and Google Analytics, what can I do with them together?" and the system responds.

The agentic layer goes one step further: **the system proactively does this for the user on a schedule**, without prompting. It inspects all connected sources for an account, discovers potential relationships and cross-source opportunities, generates hypotheses, filters for quality and novelty, and surfaces the best ones as insights in the UI (and optionally via email digest). The user wakes up to a feed of "here are 3 things we noticed about your data."

This requires Celery + Redis (the `core / infrastructure` deferred item below) and a rich enough catalog to reason over — so it depends on multiple sources being connected and synced.

---

### The Agent Pipeline

This is a **multi-step deterministic pipeline** (not a free-form ReAct loop). Each step has a clear input and output. LLM calls are made at specific steps; the overall control flow is Python, not an LLM deciding what to do next. This makes the system debuggable and cost-controllable.

```
For each account with 2+ synced sources:

  Step 1: Source Inventory
    → Gather all connected sources with their sync status and catalog metadata

  Step 2: Source Pair Analysis
    → For each pair (or combination) of sources, score cross-source potential

  Step 3: Relationship Discovery
    → For high-potential pairs, identify concrete join opportunities and
      semantic overlaps via LLM

  Step 4: Hypothesis Generation
    → For each relationship, generate specific insight hypotheses (what
      a business analyst could actually discover)

  Step 5: Quality Scoring and Deduplication
    → Score hypotheses; compare to existing insights; discard duplicates
      and low-quality suggestions

  Step 6: Insight Generation
    → Write full insight text for surviving hypotheses using the existing
      LLM insight pipeline

  Step 7: Storage and Notification
    → Persist as Insight records; queue in-app notification or email digest
```

---

### Step 1: Source Inventory

Fetch all `Source` records for the account where `last_synced_at` is not null (i.e., at least one sync has completed). For each source, gather:

- Source type (PostgreSQL, HubSpot, Google Analytics, etc.)
- Tables discovered (names, row counts, LLM descriptions if available)
- Column names and types (used for join key discovery)
- Last sync time (used to skip stale sources)

Group sources by their `SourceType.category` (e.g., `crm`, `analytics`, `database`, `ecommerce`, `support`). This category grouping will be used in Step 2 to apply known cross-domain patterns before doing any LLM reasoning.

---

### Step 2: Source Pair Scoring (Pre-LLM Filter)

Before making any LLM calls, score every source pair for cross-source potential. This is a cheap, deterministic pre-filter to avoid burning LLM tokens on hopeless combinations.

**Signal 1: Known cross-domain relationship matrix**

Some source type combinations are known to have high analytical value:

| Source A | Source B | Opportunity |
|---|---|---|
| CRM (HubSpot, Salesforce) | Web Analytics (GA, Mixpanel) | Marketing attribution — correlate campaign touches with CRM outcomes |
| CRM | E-commerce (Shopify, Stripe) | Customer lifetime value, deal-to-purchase conversion |
| CRM | Support (Zendesk, Intercom) | Customer health, churn signal detection |
| E-commerce | Analytics | Funnel analysis, cart abandonment |
| Database (Postgres) | Any SaaS | Operational data vs. tool data enrichment |

Pairs with a known pattern score higher automatically.

**Signal 2: Shared column name fingerprints**

Scan column names across both sources for likely join keys. Look for columns matching patterns like:

- `email`, `email_address`, `contact_email` (exact match of a semantic family)
- `user_id`, `userId`, `customer_id`, `account_id`, `contact_id`
- `date`, `created_at`, `event_date`, `timestamp`, `session_date`

Any pair sharing at least one likely join key scores much higher. Use a simple normalized name comparison (lowercase, strip underscores/camelCase) — no LLM needed here.

**Signal 3: Temporal overlap**

Both sources have date-typed columns covering a common time range → higher score. Both have event-style tables with timestamps → potential for time-series correlation.

Only source pairs scoring above a threshold advance to Step 3. For accounts with many sources, this keeps LLM call count bounded.

---

### Step 3: Relationship Discovery (LLM)

For each high-scoring pair, make an LLM call with a structured output prompt. The goal is to identify **specific join strategies** — not vague suggestions, but concrete table.column → table.column relationships.

**Prompt inputs:**
- Source A name and type
- Source A table/column summary (generated from catalog metadata — same DDL-like format as text-to-SQL)
- Source B name and type
- Source B table/column summary
- Any pre-identified join key candidates from Step 2

**Prompt asks for structured JSON output:**

```json
{
  "join_opportunities": [
    {
      "source_a_table": "contacts",
      "source_a_column": "email",
      "source_b_table": "ga_events",
      "source_b_column": "user_email",
      "confidence": "high | medium | low",
      "join_type": "direct | fuzzy | temporal",
      "reasoning": "Both tables contain email addresses..."
    }
  ],
  "semantic_overlaps": [
    {
      "concept": "customer lifecycle stage",
      "source_a_signal": "deal_stage in opportunities table",
      "source_b_signal": "conversion_event in ga_events",
      "reasoning": "..."
    }
  ]
}
```

Store these as `CrossSourceRelationship` records (see data model below) — they are reusable across runs and don't need to be rediscovered every time.

---

### Step 4: Hypothesis Generation (LLM)

For each confirmed relationship or semantic overlap from Step 3, generate specific insight hypotheses. This is a second LLM call, now focused on analytical value rather than structural discovery.

**Prompt asks:** "Given that these two sources can be joined on X, what are 3–5 specific, actionable insights a business analyst could extract? Be concrete — name the metrics, the expected patterns, and the business decision each insight supports."

**Structured output:**

```json
{
  "hypotheses": [
    {
      "title": "Marketing Channel → CRM Win Rate",
      "description": "Join GA session source with Salesforce closed-won deals to identify which marketing channels produce the highest-quality leads by revenue.",
      "business_value": "Reallocate ad spend toward channels with highest revenue per lead, not just highest lead volume.",
      "join_strategy": "Match ga_sessions.email to salesforce_opportunities.contact_email, group by ga_sessions.utm_source",
      "required_data": ["ga_sessions.utm_source", "salesforce_opportunities.stage", "salesforce_opportunities.amount"],
      "specificity_score": 0.9
    }
  ]
}
```

The `specificity_score` field is returned by the LLM as a self-assessment — prompts that produce vague output are pre-filtered before Step 5.

---

### Step 5: Quality Scoring and Deduplication

**Quality filter:** Discard hypotheses where:
- `specificity_score < 0.6` (LLM flagged its own output as vague)
- Title/description is generic (pattern-match against known vapid phrases: "gain insights", "better understand your data")
- Required data columns don't exist in the actual catalog (validate against `catalog.Column` records)

**Deduplication:** For each surviving hypothesis, generate an embedding of its title + description. Compare against embeddings of existing `Insight` records for this account (using cosine similarity via pgvector). If similarity exceeds a threshold (~0.85), skip — this insight is already known.

This means the embedding index built for text-to-SQL (Step 2 in the queries section) also serves deduplication here. Same infrastructure, second use case.

**Rate cap:** Don't surface more than N new agent-discovered insights per account per run (e.g., 5). Rank survivors by specificity score + source pair novelty score; take the top N.

---

### Step 6: Insight Generation

Pass surviving hypotheses into the existing `apps/insights/` LLM pipeline (the same abstraction used for table descriptions) with a prompt variant tuned for cross-source narrative insight. The output is a full, user-readable insight that:

- Explains **what** the data combination reveals
- Gives a concrete **how** (what to join, what to measure)
- States the **business decision** it supports

This reuses the existing `Insight` model with `insight_type = 'cross_source_agent'` and `status = 'pending_review'` (surfaced in a review queue before becoming fully published, at least initially).

---

### Step 7: Storage and Notification

**Storage:**

- `Insight` records with `insight_type='cross_source_agent'`, linked via `InsightTarget` to both source records
- `AgentInsightRun` records tracking each pipeline execution (see data model below)
- `CrossSourceRelationship` records persisted and reused across runs

**Notification options** (start simple, expand later):

- **In-app:** A "Discovered Insights" section in the dashboard showing `pending_review` agent insights with accept/dismiss actions
- **Email digest:** Weekly summary ("We found 3 new opportunities across your connected sources") — use Django's email system, plain-text to start
- **Dismissed insights:** If a user dismisses a hypothesis, store the signal; don't resurface the same pattern

---

### Data Model

New models in `apps/insights/` (or a new `apps/agents/` app if scope warrants it):

**`AgentInsightRun`** — tracks one execution of the pipeline for one account

```
AgentInsightRun
  account           FK → accounts.Account
  status            CharField     running / completed / failed / partial
  started_at        DateTimeField
  completed_at      DateTimeField (nullable)
  sources_analyzed  IntegerField  how many sources were in scope
  pairs_evaluated   IntegerField  how many source pairs were scored
  hypotheses_generated IntegerField
  insights_created  IntegerField  how many survived to storage
  error_log         TextField     any non-fatal errors during the run
  triggered_by      CharField     'schedule' / 'new_source' / 'manual'
```

**`CrossSourceRelationship`** — a discovered join opportunity between two sources; reused across runs

```
CrossSourceRelationship
  account           FK → accounts.Account
  source_a          FK → sources.Source
  source_b          FK → sources.Source
  source_a_table    CharField     table name
  source_a_column   CharField     column name
  source_b_table    CharField
  source_b_column   CharField
  join_type         CharField     direct / fuzzy / temporal
  confidence        CharField     high / medium / low
  reasoning         TextField     LLM reasoning text
  first_discovered  DateTimeField
  last_confirmed    DateTimeField updated when still valid on re-runs
  is_active         BooleanField  False if source or column no longer exists
```

---

### Triggering Strategy

Three trigger types, all via Celery:

**1. Scheduled (Celery beat)**
Run the full pipeline for all eligible accounts once per week. "Eligible" = has 2+ sources with completed syncs, last agent run was more than 6 days ago.

**2. Event-triggered (on new source connected)**
When a user connects and successfully syncs a new source, fire the pipeline for that account via a Django signal → Celery task. This is the highest-value trigger: the user just expanded their data landscape and cross-source opportunities just changed.

**3. Manual (via UI)**
A "Run discovery" button in the insights section for accounts that want on-demand analysis. Rate-limited to once per 24 hours.

---

### Cost and Quality Controls

LLM calls per account per run scale with the number of source pairs, not the number of tables. With 3 sources, there are 3 pairs; with 5 sources, 10 pairs. Keep this in mind:

- **Pre-filter aggressively in Step 2.** The pair scoring step should eliminate most combinations before any LLM calls are made.
- **Cap LLM calls per run.** Set a max (e.g., 10 LLM calls per account per run) and prioritize highest-scoring pairs. Log when the cap is hit.
- **Cache Step 3 results.** `CrossSourceRelationship` records don't need to be rediscovered every run. Only redo Step 3 for pairs where a new sync has added significant new tables/columns since the last discovery.
- **Use cheaper models for Step 2 filtering and Step 3 discovery.** Reserve the better model for Step 6 (the actual insight writing that the user will read).

---

### Phased Build

1. **Phase 1 — Manual trigger only, single source pair**
   Build the pipeline end-to-end but only for user-initiated runs on one explicitly selected source pair. No scheduling, no Step 2 scoring. Good for validating prompt quality and the review workflow.

2. **Phase 2 — Multi-pair with scoring, event-triggered**
   Add Step 2 pair scoring. Trigger the pipeline automatically when a new source is connected. Store `CrossSourceRelationship` records. Introduce `AgentInsightRun` tracking.

3. **Phase 3 — Scheduled runs and deduplication**
   Add Celery beat scheduling. Add embedding-based deduplication (Step 5). Add the dismissed-insight feedback signal.

4. **Phase 4 — Email digest and quality iteration**
   Add weekly email digest. Use accumulated feedback signals (accepted vs. dismissed insights) to tune the pair scoring weights and model prompt selection.

---

### Relationship to Existing Features

- **Requires Celery + Redis** (the infrastructure deferred item below)
- **Benefits from the ontology layer** (Phase 3+ of the ontology section): if object types have been defined, the agent can reason about "Customer" rather than `tbl_cust_master`, producing much better hypotheses
- **Benefits from text-to-SQL** (queries app): the same pgvector embedding infrastructure serves both deduplication (Step 5) and text-to-SQL table selection
- **Reuses the existing LLM abstraction** from `apps/insights/` — the provider layer, prompt management, and `Insight` model are all shared; this is additive, not a rewrite

## core / infrastructure

- **Celery + Redis** — background task queue for scheduled syncs and batch insight generation
- **REST API** — `apps/api/` layer for programmatic access (post-MVP app, skip for now)
- **Scheduled syncs** — run source syncs on a cron schedule rather than manual trigger only

---

## testing

The test plan lives in `devdocs/testing.md`. The `apps.users` section is complete. The following sections are stubs that must be filled in and implemented once each app's views are built:

- **apps.sources** — source creation (valid credentials, missing fields), connection test (success and failure), sync trigger
- **apps.catalog** — schema/table/column list views return 200, all views are scoped to the correct account (no cross-tenant data leakage)
- **apps.insights** — insight generation triggers LLM call (mock the LLM), insight list and detail views return 200

When each section is filled in, run the full test suite (`python manage.py test`) before marking it done. Multi-tenancy boundary tests (account A cannot see account B's data) are required for every app that touches tenant-scoped models.

---

## logging

The logging plan lives in `devdocs/logging.md`. No logging infrastructure exists yet — this is a clean addition post-MVP. Work to complete:

- **settings.py** — add the `LOGGING` dict with console handler (dev) and file handler (production)
- **apps.accounts** — instrument `TenantMiddleware`: successful account resolution, missing membership warning
- **apps.users** — instrument registration and login/logout events (user ID only, never email or password)
- **apps.sources** — instrument encryption operations, source creation, and sync lifecycle (start, complete, fail)
- **apps.catalog** — instrument metadata sync: schema/table/column discovery counts, skipped objects, completion summary
- **apps.insights** — instrument LLM calls: provider, model, token usage, retries, failures (never log prompt or response content)

Review the "What NOT to Log" section in `devdocs/logging.md` before instrumenting any app. Credentials, tokens, and LLM content are never logged at any level.

---

## queries (new app — Natural Language to SQL)

### Overview

Build text-to-SQL natively using the LLM abstraction layer already planned for `apps/insights/`. No third-party text-to-SQL product is required. The catalog metadata (schemas, tables, columns, FK relationships, LLM-generated descriptions) provides the schema context, making this feature a direct downstream beneficiary of everything built for the `catalog` and `insights` apps.

Lives in a new `apps/queries/` app (already identified as a Phase 4 app in `devdocs/architecture.md`).

### How It Works

1. **Schema context builder** — formats catalog metadata as DDL strings suitable for prompt injection. Reconstruct `CREATE TABLE` statements from `Schema`, `Table`, and `Column` models, including FK relationships and any LLM-generated column descriptions as inline SQL comments.

2. **Table selection** — for small schemas, inject all tables. For large schemas (many tables), use embedding-based retrieval to select only the relevant tables per query:
   - During catalog sync, embed each table's metadata (name + column names/descriptions) using the OpenAI or Anthropic embeddings API
   - Store embeddings using pgvector (a PostgreSQL extension — no separate vector database needed)
   - At query time, embed the user's question and retrieve the top-K most semantically similar tables

3. **SQL generation** — send selected schema context + user question to the LLM. Prompt should:
   - Instruct the model to return only a SELECT statement, no other statement types
   - Include 2–5 few-shot question/SQL examples for the specific data source
   - Include a chain-of-thought step for complex queries (optional, adds latency)

4. **SQL validation** — before execution, validate the generated SQL with `sqlglot` (pure Python SQL parser). Check that the statement type is `SELECT`; block INSERT, UPDATE, DELETE, DROP, etc. Also pattern-match for dangerous keywords as a secondary defence.

5. **Read-only execution** — execute against the source database using a separate read-only database role with no write permissions. Apply `SET statement_timeout = '30s'` before executing. Enforce a row limit by appending/overwriting the LIMIT clause in the parsed AST.

6. **Results UI** — always show the generated SQL (collapsible, syntax-highlighted). Show results in a paginated table. Offer CSV export. Provide a "refine" input for follow-up questions.

### Key Libraries

| Library | Purpose |
|---|---|
| `sqlglot` | SQL parsing, statement-type validation, AST manipulation (add LIMIT) |
| `pgvector` | Embedding storage in PostgreSQL for table selection RAG |
| existing LLM abstraction | Shared with `apps/insights/` — no new LLM plumbing needed |
| `celery` | Run LLM calls + SQL execution off the request cycle (long-running) |

### Execution Safety Checklist

- Read-only PostgreSQL role on the customer's database (documented in source setup)
- `statement_timeout` set per execution
- `LIMIT` enforced via AST manipulation (not just appended as a string)
- `sqlglot` parse validates statement type before execution
- User's natural language question goes only to the LLM, never interpolated into SQL
- All executions logged (user, question, generated SQL, duration, row count)

### Phased Build

1. **Phase 1 (MVP queries)** — prompt construction from catalog, single LLM call, sqlglot validation, read-only execution, basic results table with SQL preview
2. **Phase 2 (scale)** — pgvector table selection for large schemas; capture FK constraints and column stats during sync
3. **Phase 3 (quality)** — thumbs up/down feedback; save successful Q/SQL pairs as source-specific few-shot examples; dynamic few-shot retrieval
4. **Phase 4 (UX polish)** — SSE streaming, multi-turn conversation context, query history, CSV export

### Integration with Catalog

The virtuous cycle: richer catalog metadata → better SQL generation. Specifically:
- LLM-generated table/column descriptions from `apps/insights/` are injected into the SQL prompt as inline DDL comments
- FK constraints captured during sync enable correct JOIN generation
- Column statistics (null fraction, distinct count, common values) captured during sync give the LLM filter context
- Successful Q/SQL pairs are stored per-source and become few-shot examples for that source

---

## Amundsen Integration

### Overview

[Amundsen](https://www.amundsen.io) is an open source data discovery and metadata engine (Linux Foundation AI & Data). It is widely deployed at data-mature organizations. Flint's opportunity is to be the **AI intelligence layer on top of Amundsen** — enriching it with LLM-generated descriptions that Amundsen itself has no mechanism to produce.

Amundsen has no LLM layer, no auto-generated descriptions, and no data profiling. That gap is exactly Flint's value proposition.

### Integration Patterns

**Pattern A — Push LLM insights to Amundsen (primary value)**

For accounts that self-host Amundsen, add an optional "export to Amundsen" toggle in source settings. After generating LLM table/column descriptions, push them to Amundsen's Metadata Service REST API:

```
PUT /table/{table_uri}/description       # push table description
PUT /column/{column_uri}/description     # push column description
PUT /table/{table_uri}/owner             # push ownership
POST /table/{table_uri}/badges           # push LLM-generated tags
```

Amundsen's table URI format: `{database}://{cluster}.{schema}/{table_name}` — e.g., `postgresql://prod.public/orders`.

This positions Flint as a value-add service for organizations already invested in Amundsen. The pitch: "Flint generates the descriptions; your Amundsen instance surfaces them."

**Pattern B — Use Databuilder extractors for Phase 3+ connectors**

`amundsen-databuilder` is a pip-installable Python library that contains battle-tested metadata extractors for BigQuery, Snowflake, Redshift, Hive, dbt, Tableau, and more. Rather than writing native connectors from scratch for every Phase 3+ data warehouse, evaluate whether Databuilder's extractor classes can be used inside Flint's sync pipeline to populate `catalog.Table` and `catalog.Column` records.

The extractor model: each extractor implements a `next_record()` method returning `TableMetadata` objects. These can be adapted to populate our own Django models without loading anything into Amundsen's Neo4j backend.

```python
# Pseudocode — use a Databuilder extractor in a Django management command or Celery task
from databuilder.extractor.bigquery_metadata_extractor import BigQueryMetadataExtractor

extractor = BigQueryMetadataExtractor()
extractor.init(conf)
while record := extractor.extract():
    # map record fields to our catalog.Table / catalog.Column models
    ...
```

**What not to do:** Do not deploy Amundsen's services (Neo4j + Elasticsearch + three Flask microservices) as part of Flint. The infrastructure overhead is significant and unnecessary when you can call the REST API against a user-hosted instance or use just the Databuilder library.

### Where This Fits

- **Near-term:** Databuilder extractors are relevant when building Phase 3 data warehouse connectors (Snowflake, BigQuery, Redshift). Evaluate extractor quality against what a native connector would produce before committing.
- **Medium-term:** Amundsen API push is a differentiated enterprise feature. Target organizations that already have Amundsen deployed and want it enriched.
- **No urgency:** There is no reason to integrate with Amundsen before Phase 2 is complete. Catalog metadata must be rich and LLM descriptions must be working before an Amundsen export is useful.

### Note on Alternatives

Amundsen's community velocity has slowed (2023–2025). DataHub (LinkedIn open source) and OpenMetadata are more actively maintained alternatives with similar REST API patterns. The same push-descriptions-via-REST-API integration approach applies to either. Design the export abstraction as a pluggable "catalog export target" rather than hardcoding Amundsen specifically.

---

## ontology (new app — Business Ontology Layer)

### Overview

A semantic mapping layer that sits between raw database schema (physical metadata in `apps/catalog/`) and business users and AI agents. Maps cryptic physical names to meaningful business concepts:

- `tbl_cust_master` → **Customer** object type
- `contact_email_addr` → **email** property
- `ord_hdr.cust_id → tbl_cust_master.cust_id` → Customer **has many** Orders

The ontology is a **description of data, not a copy of it**. It stores mappings; it does not store rows. All data stays in the source database.

### Why Build This

- Enables AI agents to work with business concepts (`Customer.email`) rather than physical schema (`tbl_cust_master.contact_email_addr`). Dramatically improves LLM query quality.
- Gives non-technical users a business vocabulary for exploring data.
- Makes the text-to-SQL feature more accurate — the LLM works against clean, labelled schema.
- Long-term: the ontology becomes the function/tool definition source for LLM agents — a safe, typed API boundary between AI and raw data.

### Data Model

Lives in a new `apps/ontology/` app. Core models:

**`ObjectType`** — a named business entity backed by one (or more) catalog tables

```
ObjectType
  name              CharField          "Customer"
  display_label     CharField          "Customer"
  description       TextField          LLM-written or human-written
  source_table      FK → catalog.Table  the primary backing table
  pk_column         FK → catalog.Column which column is the entity's identity
  is_published      BooleanField       draft vs. visible to users
  suggested_by_llm  BooleanField       tracks LLM-generated drafts
  account           FK → accounts.Account  (tenant-scoped)
```

**`ObjectTypeProperty`** — a named field on an ObjectType, sourced from a Column

```
ObjectTypeProperty
  object_type       FK → ObjectType
  name              CharField          "email"
  display_label     CharField          "Email Address"
  description       TextField
  source_column     FK → catalog.Column
  is_visible        BooleanField       can suppress internal/audit columns
  suggested_by_llm  BooleanField
```

**`ObjectTypeLink`** — a named, typed relationship between two ObjectTypes

```
ObjectTypeLink
  source_object_type   FK → ObjectType
  target_object_type   FK → ObjectType
  name                 CharField         "has_orders"
  display_label        CharField         "Has Orders"
  cardinality          CharField         one_to_many / many_to_one / many_to_many / one_to_one
  join_column          FK → catalog.Column  the FK column that backs this link
  suggested_by_llm     BooleanField
```

**`LLMOntologySuggestion`** — stores raw LLM output pending human review

```
LLMOntologySuggestion
  source_table   FK → catalog.Table
  raw_suggestion JSONField             full structured output from LLM
  status         CharField             pending / accepted / rejected / partial
  reviewed_by    FK → users.User
  reviewed_at    DateTimeField
  notes          TextField             reviewer notes on partial accepts
  account        FK → accounts.Account
```

### LLM-Assisted Suggestion Workflow

Given a `catalog.Table` with its related `Column` records and FK relationships, construct a prompt that asks the LLM to return structured JSON:

```
{
  "object_type_name": "Customer",
  "display_label": "Customer",
  "description": "A person or organization that has purchased...",
  "primary_key_column": "cust_id",
  "properties": [
    {
      "name": "email",
      "display_label": "Email Address",
      "source_column": "contact_email_addr",
      "description": "Primary contact email"
    },
    ...
  ],
  "suggested_links": [
    {
      "name": "has_orders",
      "display_label": "Has Orders",
      "direction": "outbound",
      "related_table": "ord_hdr",
      "cardinality": "one_to_many"
    }
  ]
}
```

Use the shared LLM abstraction from `apps/insights/`. This uses the same provider layer, same credential management. No new LLM plumbing required.

The LLM is particularly good at this task because column naming patterns (`cust_id`, `prd_desc`, `ord_dt`) are well-represented in training data. Quality on real-world enterprise schemas is high.

### Review UI (HTMX pattern)

A review queue at `/ontology/review/` lists pending `LLMOntologySuggestion` records. Each suggestion shows:

- Proposed object type name and description (accept/edit/reject)
- Each proposed property as a row (accept individually or bulk-accept)
- Each proposed link (accept/reject)

HTMX is a natural fit: each accept/reject button posts to a Django view that creates the corresponding `ObjectType`, `ObjectTypeProperty`, or `ObjectTypeLink` record and swaps the row state in-place (no page reload).

### URL Structure

```
/ontology/                          list of all published ObjectTypes
/ontology/<id>/                     detail view: properties + links
/ontology/<id>/edit/                edit name/label/description
/ontology/suggest/<table_id>/       trigger LLM suggestion for one table
/ontology/review/                   queue of pending LLM suggestions
/ontology/review/<id>/              review and accept/reject a suggestion
/ontology/graph/                    relationship graph visualization
```

### Graph Visualization

The relationship graph can be rendered using `vis.js` or `cytoscape.js` with data supplied as JSON from a Django view:

```json
{
  "nodes": [{"id": 1, "label": "Customer"}, {"id": 2, "label": "Order"}],
  "edges": [{"from": 1, "to": 2, "label": "has orders", "cardinality": "1:N"}]
}
```

No server-side graph library required — the Django view queries `ObjectType` and `ObjectTypeLink` and serializes to JSON.

### Phased Build

1. **Phase 2 — Manual object type definitions** — build the models and CRUD UI; no LLM yet; let users map tables to business names manually; useful immediately as semantic documentation
2. **Phase 3 — LLM suggestion + review workflow** — add `LLMOntologySuggestion`, the suggestion service, and the review UI
3. **Phase 4 — Link modeling and graph view** — `ObjectTypeLink` CRUD; relationship graph visualization
4. **Phase 5 — Live queryable objects** — services that execute queries against source databases through ontology definitions, returning typed entity instances rather than raw rows; requires source credentials + connection infrastructure from `apps/sources/`
5. **Phase 6 — AI agent integration** — the ontology becomes the tool/function definition source for LLM agents; enables a safe "ask your data" experience where the LLM works with business concepts rather than raw SQL

### Key Architectural Invariant

The ontology is a **projection, not a store**. It describes how to interpret data; it does not copy or cache rows. All foreign keys in the ontology models point at `catalog.Table` and `catalog.Column` — the physical metadata that was synced from the source. When the source schema changes, the ontology definitions that reference renamed or dropped columns should be flagged as stale (schema drift detection, already a potential feature in `potential_features.md`).

# Use frontend-design plugin to iterate on UI

# ~~Change App Name to 'Flint'~~ COMPLETE
* ~~Update all references to 'Luminetiq'~~ DONE
* Create logo and add to UI

# DEMO MODE
* Add a demo mode to the UI
* Have claude mock up data locally for a few connectors that will generate interesting cross source insights