# Post-MVP: Deferred Features

Concrete features that are out of scope for the MVP but will need to be built. Organized by app.

For speculative or longer-horizon ideas, see `devdocs/potential_features.md`.

---

## Suggested Build Order (as of 2026-04-15)

**Phase 2 — Standalone features, no infrastructure dependencies**
1. ~~Account settings page (rename account) — `accounts`~~ COMPLETE
2. ~~Insight approval/rating (thumbs up/down) — `insights`~~ COMPLETE
3. ~~Domain-based registration guard — `accounts`~~ COMPLETE
4. ~~Team invites — `accounts`~~ COMPLETE
5. ~~Loading indicators for source sync and use case generation — `sources`, `insights`~~ COMPLETE
6. ~~Tailwind CDN → production build — `infrastructure`~~ COMPLETE

**Phase 3 — Requires Celery + Redis first**
7. ~~Celery + Redis setup — `core/infrastructure`~~ COMPLETE
8. ~~Batch table description generation — `insights`~~ COMPLETE — scope pivoted from bulk fan-out to async-on-first-view; see `devdocs/featuredocs/async-table-descriptions.md` for the rationale
9. ~~Draft a README based on what exists so far — `general`~~ COMPLETE
10. ~~Scheduled syncs — `sources`~~ COMPLETE (Phases 1 & 2) — see `devdocs/featuredocs/scheduled-syncs.md`. Phase 3 automated tests moved to `devdocs/testing.md` under `apps.sources`; will be written in the Phase 6 testing pass (#24).
10b. ~~Source Detail Updates~~ COMPLETE — see `devdocs/featuredocs/source-detail-updates.md`. Delivered 10c/10d/10e plus follow-ons: table-detail card reorder, LLM prompt heading removal, and two bug fixes (use-cases gate vs. async overview; sync-status partial leaking the history table into the header).
    10c. ~~Source Overview async-on-first-view: show a spinner in the card and swap in the content when ready, matching the other async-on-first-view pages.~~ COMPLETE
    10d. ~~Move Sync Schedule + Sync History into a right-hand column beside Source Overview / Schemas & Tables (3/5 + 2/5 split).~~ COMPLETE
    10e. ~~Swap Source Overview and Schemas & Tables cards.~~ COMPLETE
10f. ~~Delete source → cascade-clean its insights~~ COMPLETE — see `devdocs/featuredocs/source-delete-insight-cleanup.md`. Added a `pre_delete` signal on `Source` (`cleanup_insights_on_source_delete` in `apps/sources/signals.py`) that hard-deletes source-targeted (Source Overview, use-case) and table-targeted (table-description) `Insight` rows — which cascade their `InsightTarget`s — before the source and its tables are removed. Scoped by account; manually verified via the UI. Automated tests deferred to the Phase 6 testing pass (`devdocs/testing.md` → `apps.sources`). Found during the 10b work; split to its own branch to keep that one focused.
11. ~~Agentic cross-source discovery (**Phase 1 only** — manual pair trigger + accept/dismiss review) — `insights`~~ **COMPLETE (Phase 1 build; automated tests deferred to the Phase 6 testing pass #24, written up in `devdocs/testing.md`)** — see `devdocs/featuredocs/agentic-cross-source-discovery.md`. **Scope narrowed (2026-07-02):** shipped only the manual, user-triggered single-pair discovery with a review (accept/dismiss) workflow — this reaches parity with intra-source use cases and lets us validate the feature before investing further. Delivered: models/migrations, prompt module, service methods (both providers), the `run_discovery_for_pair` pipeline + storage, the Celery task, all five views + URLs, the three templates, and the dashboard "Cross Source Use Cases" card + "Discover" nav link. The automation layer (pair scoring, scheduling, embedding dedup, event triggers) is deferred to build item **22b** (Phase 5b) below.
11b. ~~Convert intra-source use-case generation to async + make regeneration non-destructive — `insights`~~ **COMPLETE (2026-07-19)** — see `devdocs/featuredocs/async-use-cases.md`. Shipped the async-on-first-view conversion (`generate_intra_source_use_cases_task` in `apps/insights/tasks.py`, `pending` placeholder + poll via the existing `use_cases_status` endpoint), non-destructive newest-first regeneration (removed the delete-before-LLM block), a fixed-height scrollable card, and an `active`-only rate-limit guard so a pending/failed placeholder doesn't skew the 24h window. Retry reuses the Generate/Regenerate control (no dedicated route). Verified end-to-end on `feature/async-use-cases` (merged); automated tests deferred to the Phase 6 testing pass (#24).
12. ~~Demo Mode Phase 2 (product scenario + auto-trigger insights after load)~~ **DESCOPED (2026-07-06)** — retiring the remaining Demo Mode phases. Cross-source discovery (#11) already works on demo sources via its manual trigger (demo sources sync into the catalog like any other source), which covers the demo value we were chasing; the product-scenario dataset and auto-triggering insights on load aren't worth the build. See the Demo Mode section's Phased Build below (Phase 2 & 3 both marked descoped).

**Phase 4 — New apps and connector expansion, depend on Phase 2 & 3**
13. PyAirbyte integration — `sources` — adapter that lets us register PyAirbyte sources (300+) via the same `BaseConnector` interface used today, so catalog/insights/agentic discovery work uniformly across native and Airbyte-backed sources
14. First SaaS connector batch via PyAirbyte — HubSpot, Salesforce, Stripe — `sources` — chosen to match the existing Sales demYouo scenario (HubSpot) and the most common enterprise CRM/payments use 
    cases. Native connectors only where deep metadata extraction is needed; everything else routes through the PyAirbyte adapter from #13.
15. Queries app (natural language to SQL) — `queries`
16. Query client — `queries` — a UI to run queries against a source and view results: the LLM-generated SQL from the queries app, the starter SQL on generated use case suggestions, and ad-hoc 
    queries the user writes themselves. Results are displayed only, never persisted (Flint does not store source data). Two separate implementations:
    - A "run query" button on the source detail page,
    - A dedicated query page with a query editor and results viewer for the new queries app for natural language to sql queries
17. ERD generator/viewer — `catalog` — visual entity-relationship diagrams generated from catalog FK metadata, with optional LLM-inferred relationships and ontology-aware labelling
18. Ontology app Phase 1 (manual object type definitions) — `ontology`
19. SaaS connector batch 2 via PyAirbyte — Google Analytics, Intercom, Shopify, Zendesk, Mixpanel, Amplitude, Segment — `sources` — broadens go-to-market coverage; aligns with the Product demo scenario (Intercom) and common e-commerce/support stacks
20. Data warehouse + storage connectors — Snowflake, BigQuery, Redshift, S3/GCS — `sources` — opens the warehouse path; PyAirbyte adapter for most, with native connectors only where deep metadata extraction (FK constraints, column statistics) justifies the work

**Phase 5 — Advanced / long-horizon**
21. Multi-account switching, role-based permissions — `accounts`
22. Ontology Phases 2–6 (LLM suggestions, graph view, agent integration)

**Phase 5b — Cross-Source Discovery Automation** (deferred until the Phase 1 manual feature — build item #11 — has proven out)
22b. Agentic cross-source discovery — **Phases 2 & 3** — `insights` — the automation layer built on top of the shipped Phase 1 manual feature (#11). Deferred deliberately: Phase 1 (manual single-pair trigger + accept/dismiss review) ships and gets validated first, so we don't build scheduling/scoring/dedup before knowing the core discovery is worth automating.
    - **Phase 2 — multi-pair, scored, event-triggered.** Add the `AgentInsightRun` and `CrossSourceRelationship` models (fields per the Data Model in the detailed section; `CrossSourceRelationship` doubles as a reuse cache so Step 3 only re-runs for pairs with new catalog rows). Add Step 1 `gather_source_inventory(account)` and Step 2 `score_source_pair` — a deterministic, **structural-only** ranker (shared column-name fingerprints + temporal overlap, **no** `SourceType.category` matrix — see the "no source-type bias" decision in the detailed section) that *orders* which pairs spend the per-run LLM-call cap rather than hard-gating. Event trigger: when a source finishes its **first** successful sync (`apps/sources/tasks.py::sync_source_task` completion path or a signal), enqueue the full-account pipeline if the account now has 2+ synced sources (`triggered_by='new_source'`). Extend the Phase 1 button to also offer a full-account run (`triggered_by='manual'`).
    - **Phase 3 — scheduled + deduped.** Celery-beat weekly run for every eligible account (2+ synced sources, last `AgentInsightRun` > 6 days ago; `triggered_by='schedule'`). Embedding-based dedup (Step 5): requires the **Postgres + pgvector** move (also a queries-app prerequisite) and a new embeddings call path on `BaseService` (does not exist today) — cosine similarity > ~0.85 against existing account insights → skip as already-known. Quality filter (can land earlier): drop `specificity_score < 0.6`, vapid-phrase titles, and `required_data` columns absent from `catalog.Column`. Persist a dismissed-hypothesis fingerprint so near-matches aren't resurfaced.
    - **Full spec** — pipeline Steps 1–7, exact model fields, triggering strategy, and cost/quality controls — lives in the "insights — Agentic Cross-Source Discovery" detailed section below (the Phased Build there labels these Phases 2–3, with the descoped email-digest/multi-source items as 4–5). Tests for this work are listed in the featuredoc's (now-removed) Phase 2/3 blocks — re-derive them from the detailed section when this is picked up.

---
## Phase 6 — General

Cross-cutting cleanup items addressed after all feature work in this doc is complete. Numbers match the build order above.

23. **Add docstrings to all files** — sweep every module and add module- and function-level docstrings. Task Claude to find all files currently missing them.
24. **Address `devdocs/testing.md` in full** — fill in the stubbed test sections for each app (`apps.sources`, `apps.catalog`, `apps.insights`), write the tests, and run the full suite (`python manage.py test`) until it passes. Multi-tenancy boundary tests (account A cannot see account B's data) are required for every tenant-scoped app.
25. **Address `devdocs/logging.md` in full** — add the `LOGGING` config to `settings.py` and instrument every app per the logging plan (tenant middleware, auth events, sync lifecycle, LLM calls). Never log credentials, tokens, or LLM prompt/response content.
26. **Run the bug bash** — broad sweep for bugs, dead code, and rough edges across the codebase; produce a single triaged punch list (see the "bug bash" section below). Find, don't fix — fixes happen in follow-up sessions. **Items already found during feature work are accumulating in `devdocs/bug_bash.md`** — start there, then sweep for the rest.
27. **Add AI evals** — build an evaluation harness for the LLM-generated outputs (table descriptions, source overviews, use case suggestions, cross-source insights) so quality regressions are caught as prompts and models change.
28. **Update the README** — revise the README drafted in build order item #9 so it reflects the final feature set.

> **Ordering note:** Do not start testing, logging, or the bug bash until all feature work in this doc is complete.


---

## ~~sources — Intra-Source Suggested Use Cases~~ COMPLETE (Phases 1 & 2)

### Overview

On the source detail page, directly below the Source Overview section, add a **"Suggested Uses"** section. This section contains a set of cards, each describing a specific analytical use case that can be derived by combining two or more tables within the same source. Each card also includes an AI-generated starter SQL query so the user can immediately act on the suggestion.

This is the single-source counterpart to the cross-source agentic discovery feature (see the `insights — Agentic Cross-Source Discovery` section). That feature surfaces what's possible *across* sources; this surfaces what's possible *within* one source. Single-source suggestions are cheaper to generate, require no cross-source join reasoning, and are immediately actionable with the credentials the user has already connected.

**Example cards for a music store database:**
- *"Analyze customer purchase patterns"* — Join `Customer`, `Invoice`, and `InvoiceLine` to calculate average order value, purchase frequency, and top-spending customers. Starter SQL: a CTE grouping invoices by customer with `SUM(total)` and `COUNT(*)`.
- *"Track catalog performance by genre"* — Join `Track`, `Genre`, `InvoiceLine` to identify which genres generate the most revenue. Starter SQL: `GROUP BY genre.name ORDER BY revenue DESC`.
- *"Identify employee sales performance"* — Join `Employee`, `Customer`, `Invoice` to see which support reps are linked to the most revenue.

---

### Where It Lives in the UI

The section appears on `sources/source_detail.html`, below the existing Source Overview card. It uses the same card visual style as the rest of the page. Each use case card contains:

1. **Title** — a short, plain-English name for the use case (e.g., "Customer Purchase Pattern Analysis")
2. **Description** — 2–3 sentences explaining what insight can be derived and why it's useful
3. **Tables involved** — a row of small badges naming each table used (e.g., `Customer` `Invoice` `InvoiceLine`)
4. **Starter SQL** — a collapsible code block with a real, runnable SELECT query against the source's actual schema. The query should be genuinely useful — not a toy example — but intentionally left as a starting point (no WHERE filters, no date ranges) so the user can adapt it.

On initial page load, if no suggestions have been generated yet, show an empty state with a "Generate Suggestions" button. Once generated, suggestions are cached and displayed immediately on future loads. A "Regenerate" button allows refreshing them.

---

### How Generation Works

1. **Trigger** — manual button click ("Generate Suggestions") on first load; optionally auto-triggered after a successful sync once a Source Overview insight already exists.

2. **Prompt inputs** — the LLM is given:
   - The source name and type
   - A DDL-style summary of all tables and columns (same format as the Source Overview prompt — reconstruct `CREATE TABLE` statements from `Schema`, `Table`, and `Column` models)
   - The existing Source Overview insight text (so the LLM has high-level context about what the source is used for)
   - An instruction to generate 4–6 distinct, concrete use cases with starter SQL

3. **Structured output** — request JSON from the LLM:
   ```json
   {
     "use_cases": [
       {
         "title": "Customer Purchase Pattern Analysis",
         "description": "Join Customer, Invoice, and InvoiceLine to calculate average order value and purchase frequency per customer. Useful for identifying high-value segments and churn risk.",
         "tables": ["Customer", "Invoice", "InvoiceLine"],
         "starter_sql": "SELECT c.first_name, c.last_name, COUNT(i.invoice_id) AS purchase_count, SUM(i.total) AS total_spent\nFROM customer c\nJOIN invoice i ON i.customer_id = c.customer_id\nGROUP BY c.customer_id\nORDER BY total_spent DESC;"
       }
     ]
   }
   ```

4. **Storage** — store each use case as an `Insight` record with `insight_type='use_case_suggestion'`, linked to the source via `InsightTarget`. The full structured JSON (title, description, tables, sql) can be stored in the `text` field as JSON, or the model can be extended with a `JSONField` for structured insight data (preferred — avoids parsing JSON out of a text field at render time). The latter is a small model change worth making.

5. **Re-generation** — deletes existing `use_case_suggestion` insights for the source and reruns the prompt. Rate-limit to once per 24 hours to avoid runaway LLM costs.

---

### Relationship to Existing Code

- **Reuses the LLM abstraction** from `apps/insights/` — same provider layer, same prompt management pattern
- **Reuses `InsightTarget`** to link use case suggestions to the source record
- **Source Overview insight** is a prerequisite input — generate use cases only after a Source Overview exists; if it doesn't, prompt the user to generate one first
- **No new app needed** — lives in `apps/insights/` (generation service) and `apps/sources/` (view and template)
- **The starter SQL is display-only** — it is not executed. When the `queries` app is built (Phase 4), these starter queries become the natural seed queries for that feature.

---

### Phased Build

1. **Phase 1** — manual trigger only; generate and display cards; store as `Insight` records; collapsible SQL block
2. **Phase 2** — auto-trigger after sync when Source Overview already exists; "Regenerate" button with rate limiting
3. **Phase 3 (queries app)** — "Run this query" button that pre-populates the query builder with the starter SQL

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

## sources

- ~~**Source edit view** — allow users to rename a source or update its connection credentials. The MVP has no edit UI; sources can only be created or deleted. Needs a `SourceEditView` (likely `UpdateView`) at `/sources/<id>/edit/` with a form pre-populated from the existing `Source` record. Credential fields should remain encrypted on save (re-encrypt with Fernet if changed). Add an "Edit" link on `source_detail.html`.~~ COMPLETE (also added source delete)
- ~~**Source list filtering and search** — filter the source list by source type (e.g. PostgreSQL) and add a text search so users can find sources by name. Implement as URL query params (`?type=postgresql&q=my+db`) processed in the view's `get_queryset`; no JavaScript required.~~ COMPLETE

---

## catalog

- ~~**TableStatistics** — snapshot-based stats (row counts, column null rates, etc.); `TableStatistics` model built, PostgreSQL connector extended to query `pg_stats`, sync wiring complete, UI display on table detail page complete~~ COMPLETE (phases 1 & 2)
  - **Remaining:** Phase 3 — LLM context injection (inject column stats into prompt builder when generating table descriptions and SQL); deferred until `queries` app is built; see `devdocs/featuredocs/table-statistics.md`
- ~~**Schema filter on table list** — filter table list by source or schema (UI enhancement)~~ COMPLETE

---

## insights

- ~~**Insight list filtering and search** — filter by insight type (table description, source overview, etc.) or by source/table target, and add text search across insight content. Same URL query param approach as sources.~~ COMPLETE (also added source dropdown filtering via InsightTarget)
- **InsightBuilder** — cross-source exploration sessions; model planned (`InsightBuilder`) but deferred
- **Cross-source insights** — insights that span multiple sources or tables
- ~~**Batch insight generation** — generate descriptions for all tables in a source at once (requires Celery)~~ COMPLETE as async-on-first-view instead of bulk fan-out — see `devdocs/featuredocs/async-table-descriptions.md`. The scope pivot is documented there: bulk generation would have wasted LLM spend on tables nobody views, and forced a "click to continue" UX on large databases. The async path keeps the existing lazy-trigger behavior, just unblocks the page render.
- **Insight approval/rating** — thumbs up/down workflow so users can accept or reject generated insights
- ~~**Async intra-source use-case generation** — `generate_intra_use_case_suggestions` still runs the LLM call synchronously in the request cycle; the only generator not yet on Celery.~~ COMPLETE (2026-07-19, build-order item **11b**) — migrated to the async-on-first-view pattern and fixed the delete-before-LLM destructive-sequence bug. See `devdocs/featuredocs/async-use-cases.md`.

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

No source-type grouping is applied. (An earlier draft grouped sources by a `SourceType.category` field to drive a cross-domain matrix in Step 2; that was dropped — see Step 2 and the "Design decisions" note on source-type bias. Step 2 scores pairs on structure, not declared type.)

---

### Step 2: Source Pair Scoring (Pre-LLM Ranker)

Before making any LLM calls, score every source pair for cross-source potential. This is a cheap, deterministic, **structural-only** signal used to *order* which pairs get the per-run LLM budget first — not a hard gate that excludes pairs, and deliberately **not** based on what type the sources are.

> **Why no source-type matrix (decided):** an earlier draft had a "Signal 1" cross-domain matrix that scored pairs higher when their `SourceType.category` values were known to relate (CRM × analytics, etc.). That was dropped. A type prior bakes in exactly the assumption that suppresses the *surprising* cross-domain insights this feature exists to find, and it's largely redundant with the fingerprint signal below (same-domain sources already share `contact`/`email`/`*_id` columns). It also required a new `SourceType.category` field + a hand-maintained matrix. The fuzzy/semantic matching such a prior might have caught is already Step 3's (the LLM's) job. Reversible later if structural scoring proves to under-filter at high source counts.

**Signal 1: Shared column name fingerprints**

Scan column names across both sources for likely join keys. Look for columns matching patterns like:

- `email`, `email_address`, `contact_email` (exact match of a semantic family)
- `user_id`, `userId`, `customer_id`, `account_id`, `contact_id`
- `date`, `created_at`, `event_date`, `timestamp`, `session_date`

Any pair sharing at least one likely join key scores much higher. Use a simple normalized name comparison (lowercase, strip underscores/camelCase) — no LLM needed here.

**Signal 2: Temporal overlap**

Both sources have date-typed columns covering a common time range → higher score. Both have event-style tables with timestamps → potential for time-series correlation.

Pairs are ranked by this structural score and Step 3 runs on them highest-first up to the per-run LLM-call cap. At typical scale (2–5 sources = 1–10 pairs) every pair can advance; the cap — not a category threshold — is what keeps the LLM call count bounded as accounts grow.

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
- Includes a **starter SQL query** — a runnable cross-source query (or two separate queries if the sources can't be directly joined) that makes the insight immediately actionable. The query should reference real table and column names from the catalog and be genuinely useful, not a toy example. It is display-only at this stage; when the `queries` app is built it becomes a seed query.

This reuses the existing `Insight` model with `insight_type = 'cross_source_agent'` and `status = 'pending_review'` (surfaced in a review queue before becoming fully published, at least initially). Store the structured output (insight text + starter SQL) in a `JSONField` on `Insight` (or extend the model) rather than embedding SQL in the `text` field — this matches the approach used for intra-source use case suggestions and avoids parsing SQL out of prose at render time.

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
- **Use cheaper models for Step 3 discovery and Step 4 hypotheses.** (Step 2 is deterministic and makes no LLM calls.) Reserve the better model for Step 6 (the actual insight writing that the user will read).

---

### Phased Build

1. **Phase 1 — Manual trigger only, single source pair** — *shipping as build-order item #11; see `devdocs/featuredocs/agentic-cross-source-discovery.md`.*
   Build the pipeline end-to-end but only for user-initiated runs on one explicitly selected source pair. No scheduling, no Step 2 scoring. Good for validating prompt quality and the review workflow. **This is the deliberately narrowed scope for now** — Phases 2 & 3 below are parked under build item **22b (Phase 5b)** until Phase 1 proves out.

2. **Phase 2 — Multi-pair with scoring, event-triggered**
   Add Step 2 structural pair scoring (shared column fingerprints + temporal overlap — no source-type matrix). Trigger the pipeline automatically when a new source is connected. Store `CrossSourceRelationship` records. Introduce `AgentInsightRun` tracking.

3. **Phase 3 — Scheduled runs and deduplication**
   Add Celery beat scheduling. Add embedding-based deduplication (Step 5). Add the dismissed-insight feedback signal.

4. **Phase 4 — Email digest and quality iteration** — *descoped from the build; moved to `devdocs/potential_features.md` (Advanced Intelligence).* Weekly email digest + using accept/dismiss feedback to tune pair-scoring weights and model/prompt selection. Build later only if there's demand, not as part of shipping cross-source discovery.

5. **Phase 5 (future) — Multi-source combinations (3+ sources)**
   The whole pipeline is intentionally built around *pairs* through Phase 4 — it's cheaper, easier to validate, and the cost model (LLM calls scale with the number of pairs) assumes two sources at a time. But the most interesting cross-source insights often span three or more sources (e.g. the Sales demo scenario's CRM + Web Analytics + Customer DB joined on a shared email key). A future phase generalizes Step 3 onward to reason over a *combination* of sources, not just a pair: build N labelled DDL blocks instead of two, and surface multi-hop join chains (A↔B↔C). Defer until two-source discovery has proven its value — the combinatorial blow-up is the reason to wait: scoring every k-subset of N sources grows far faster than pairs (with 5 sources there are 10 pairs but 26 combinations of size ≥2), so Step 2 pre-filtering and the per-run LLM-call cap become load-bearing, not optional. Keep the Phase 1–4 signatures (`source_a`, `source_b`) as-is; generalize to a `list[Source]` only when this phase is actually picked up.

---

### Relationship to Existing Features

- **Requires Celery + Redis** (the infrastructure deferred item below)
- **Benefits from the ontology layer** (Phase 3+ of the ontology section): if object types have been defined, the agent can reason about "Customer" rather than `tbl_cust_master`, producing much better hypotheses
- **Benefits from text-to-SQL** (queries app): the same pgvector embedding infrastructure serves both deduplication (Step 5) and text-to-SQL table selection
- **Reuses the existing LLM abstraction** from `apps/insights/` — the provider layer, prompt management, and `Insight` model are all shared; this is additive, not a rewrite
- **`apps/insights/prompts/intra_source_use_cases.py` is the natural starting point** for the cross-source prompt — the DDL summary pattern and JSON output structure are identical; the difference is passing multiple sources' schemas instead of one

## ~~Demo Mode~~ COMPLETE (Phase 1 — Sales scenario)

### Overview

Add a demo mode that pre-loads two realistic, multi-source datasets so anyone can experience Flint's cross-source intelligence features without connecting a real database. The demo data is stored locally as JSON files and served through lightweight demo connectors that implement the same interface as real connectors — so sync, catalog browsing, insight generation, and cross-source discovery all work exactly as they would in production.

The goal is a convincing product demo: a prospect clicks "Load Demo Data", two pre-built workspaces appear (Sales and Product), and Flint immediately surfaces interesting cross-source insights.

---

### Demo Connector Architecture

Each demo source is backed by a JSON file (or set of files) in a `demo/data/` directory at the project root. A `DemoConnector` class implements the same `BaseConnector` interface as the PostgreSQL connector — `test_connection()`, `discover_catalog()`, `get_table_metadata()` — but reads from local JSON instead of a live database.

In the connector registry, demo sources are registered as normal `SourceType` records with a `is_demo=True` flag (a small model addition). During sync, the registry routes to `DemoConnector` instead of making a real network call. From the perspective of every other part of the app — catalog, insights, cross-source discovery — demo data is indistinguishable from real data.

When real connectors for HubSpot, Salesforce, etc. are eventually built, demo mode continues to work unchanged. The demo connector is never replaced — it just coexists alongside the real one.

---

### Scenario 1: Sales Intelligence

**Sources:** HubSpot (CRM), Google Analytics (web), Customer Database (PostgreSQL-style)

**HubSpot tables:**
- `contacts` — email, first_name, last_name, lifecycle_stage, lead_score, last_activity_date, company_id
- `companies` — company_id, name, industry, employee_count, annual_revenue, country
- `deals` — deal_id, company_id, contact_id, stage, amount, close_date, owner

**Google Analytics tables:**
- `sessions` — session_id, user_email, date, source, medium, campaign, pages_viewed, session_duration_sec, converted
- `page_events` — session_id, page_path, time_on_page_sec, scroll_depth_pct
- `goal_completions` — session_id, user_email, goal_name, completed_at

**Customer Database tables:**
- `customers` — customer_id, email, company_name, plan_tier, mrr, subscription_start_date, renewal_date
- `feature_usage` — customer_id, feature_name, usage_count, last_used_date
- `invoices` — invoice_id, customer_id, amount, status, due_date

**Overlap keys designed in:**
- `contacts.email` ↔ `sessions.user_email` ↔ `customers.email` — the shared join key across all three sources
- `companies.company_id` ↔ `customers.company_name` — company-level link
- `deals.stage` + `customers.plan_tier` — pipeline vs. subscription state for upgrade analysis

**Cross-source insights this enables:**
- **Upgrade candidates** — customers on `starter` plan (Customer DB) with high `session_duration_sec` and `pages_viewed` (GA) but no open deal in HubSpot → strong signal to reach out
- **Cross-sell candidates** — companies in specific industries (HubSpot) with multiple active contacts using high-value features (Customer DB feature_usage) but low `mrr`
- **Prospect strength scoring** — HubSpot leads not yet customers, scored by GA engagement: time on pricing page, campaign source, goal completions
- **At-risk renewals** — customers with upcoming `renewal_date` (Customer DB) + declining `usage_count` (feature_usage) + no recent HubSpot activity

---

### Scenario 2: Product Intelligence

**Sources:** App Database (usage), Salesforce (accounts + contracts), Intercom (customer feedback)

**App Database tables:**
- `users` — user_id, email, account_id, role, created_at, last_login_date
- `feature_events` — event_id, user_id, feature_name, event_type, occurred_at
- `sessions` — session_id, user_id, started_at, duration_sec, platform

**Salesforce tables:**
- `accounts` — account_id, name, industry, plan_tier, arr, renewal_date, csm_owner
- `contacts` — contact_id, account_id, email, role, is_champion
- `contracts` — contract_id, account_id, start_date, end_date, arr, expansion_arr

**Intercom tables:**
- `conversations` — conversation_id, user_email, subject, sentiment, created_at, resolved_at
- `feature_requests` — request_id, user_email, feature_name, vote_count, status, submitted_at
- `nps_responses` — response_id, user_email, score, comment, submitted_at

**Overlap keys designed in:**
- `users.email` ↔ `contacts.email` ↔ `conversations.user_email` ↔ `feature_requests.user_email` — shared join key
- `users.account_id` ↔ `accounts.account_id` — account-level rollup
- `feature_events.feature_name` ↔ `feature_requests.feature_name` — feature-level link between usage and requests

**Cross-source insights this enables:**
- **Feature adoption by tier** — which `plan_tier` accounts (Salesforce) are actually using each feature (App DB `feature_events`) — identifies features stuck in enterprise-only adoption
- **High-ARR customers not using key features** — `accounts.arr` (Salesforce) + low `feature_events` count for a flagship feature (App DB) → churn risk list for CSMs
- **Feature request prioritization by revenue impact** — `feature_requests` (Intercom) ranked by total `arr` of requesting accounts (Salesforce) — not just vote count
- **NPS drivers** — correlate `nps_responses.score` (Intercom) with `feature_events` activity (App DB) to identify which features drive promoter vs. detractor sentiment
- **Expansion candidates** — accounts below enterprise `plan_tier` (Salesforce) with high feature usage breadth (App DB) and positive NPS (Intercom)

---

### Data Design Principles

- **~50–100 rows per table** — enough to make insights meaningful, small enough to be readable as JSON
- **Overlap is intentional** — email addresses, account IDs, and feature names are shared across sources so cross-source joins always find results
- **Include edge cases** — a few contacts with no GA sessions, a few customers with no HubSpot deal, a few high-ARR accounts with low usage. Interesting insights come from gaps, not just matches.
- **Realistic names and values** — use plausible company names, deal stages, feature names. The data should feel real during a demo.
- **Temporal coherence** — dates should be recent (within the last 90 days) and internally consistent (subscription start before first feature event, etc.)

---

### File Structure

```
demo/
├── data/
│   ├── sales/
│   │   ├── hubspot_contacts.json
│   │   ├── hubspot_companies.json
│   │   ├── hubspot_deals.json
│   │   ├── ga_sessions.json
│   │   ├── ga_page_events.json
│   │   ├── ga_goal_completions.json
│   │   ├── customerdb_customers.json
│   │   ├── customerdb_feature_usage.json
│   │   └── customerdb_invoices.json
│   └── product/
│       ├── appdb_users.json
│       ├── appdb_feature_events.json
│       ├── appdb_sessions.json
│       ├── salesforce_accounts.json
│       ├── salesforce_contacts.json
│       ├── salesforce_contracts.json
│       ├── intercom_conversations.json
│       ├── intercom_feature_requests.json
│       └── intercom_nps_responses.json
└── connectors/
    └── demo_connector.py   # DemoConnector implementing BaseConnector
```

---

### UI Entry Point

A "Load Demo" button or link on the dashboard empty state (when no sources are connected). Clicking it:
1. Creates two `Source` records flagged as demo sources
2. Runs demo sync (reads from JSON, populates catalog)
3. Redirects to dashboard showing both sources ready

A banner on demo sources makes clear this is demo data. A "Clear Demo Data" button removes all demo sources and their catalog/insight records.

---

### Phased Build

1. **Phase 1** — `DemoConnector` + JSON data files for sales scenario only; manual "Load Demo" button; catalog populates correctly — **COMPLETE**
2. ~~**Phase 2** — product scenario data; auto-trigger insight generation (Source Overview + use case suggestions) after demo load~~ **DESCOPED (2026-07-06)** — the Phase 1 Sales scenario is enough to demo on; a second dataset and load-time auto-triggering of intra-source insights aren't worth the build. (Build-order item #12.)
3. ~~**Phase 3** — cross-source discovery runs automatically on demo data; showcase the full agentic pipeline~~ **DESCOPED (2026-07-06)** — cross-source discovery (#11) already runs on demo sources via its manual trigger, so there's nothing extra to build here to demo it. If automatic runs on demo data are ever wanted, they fall out of the general cross-source automation work (build item 22b), not a demo-specific phase.

---

## core / infrastructure

- ~~**Celery + Redis** — background task queue for scheduled syncs and batch insight generation~~ COMPLETE — see `devdocs/featuredocs/celery-and-redis-setup.md`. Source sync converted as proof-of-concept; other long-running operations still synchronous and migrate per-feature.
- **REST API** — `apps/api/` layer for programmatic access (post-MVP app, skip for now)
- ~~**Scheduled syncs** — run source syncs on a cron schedule rather than manual trigger only (build order item #10 — Celery beat configured but no schedules wired yet) This should be defined at the 
  source level. Off by default. The user should specify a schedule (hourly, daily, weekly, monthly, etc.) In the UI above the sync histroy display information on how often teh syn runs (if one is 
  setup). On the source detail page have a button/form to setup a schedule.~~ COMPLETE — see `devdocs/featuredocs/scheduled-syncs.md`

---

## testing

The test plan lives in `devdocs/testing.md`. The `apps.users` section is complete. The following sections are stubs that must be filled in and implemented once each app's views are built:

- **apps.sources** — source creation (valid credentials, missing fields), connection test (success and failure), sync trigger
- **apps.catalog** — schema/table/column list views return 200, all views are scoped to the correct account (no cross-tenant data leakage)
- **apps.insights** — insight generation triggers LLM call (mock the LLM), insight list and detail views return 200

When each section is filled in, run the full test suite (`python manage.py test`) before marking it done. Multi-tenancy boundary tests (account A cannot see account B's data) are required for every app that touches tenant-scoped models.

---

## bug bash

After feature work is complete, run a broad sweep with Claude to surface bugs, dead code, and rough edges that accumulated during fast feature iteration. The goal is a triaged punch list, not on-the-fly fixes — separate the *finding* from the *fixing* so the scope stays bounded.

> **Running list:** concrete items spotted during feature development are logged as they're found in `devdocs/bug_bash.md` (triaged by severity, with file paths and line numbers). Fold that file into the sweep below rather than rediscovering those items.

Areas to cover during the sweep:

- **Silent failure paths** — non-2xx responses from HTMX endpoints that don't surface to the user (e.g. the deferred error-path check in `devdocs/featuredocs/loading-indicators.md` — Phase B). Catalog each one and decide: surface inline, redirect with message, or genuinely safe to swallow.
- **Pre-existing destructive sequences** — operations that delete state before the operation that follows might fail (e.g. `generate_intra_use_case_suggestions` deletes existing use cases at `apps/insights/views.py:96-102` *before* the LLM call at line 105; a failed LLM call leaves the user with nothing).
- **Stale UI state** — buttons or sections rendered from page-load context that can be wrong by the time the user clicks (e.g. rate-limit guards that hide a button only at GET time).
- **Tenancy boundary checks** — every queryset on a tenant-scoped model should filter by `request.account`. Sweep all views and managers; flag any raw `Model.objects.filter(...)` without account scoping.
- **Encryption boundary** — verify credentials are decrypted only at connector instantiation and never logged, returned in JSON, or rendered in templates.
- **Missing type hints** — CLAUDE.md mandates type hints on all functions; the bash should flag any module that drifted.
- **Form widget styling** — CLAUDE.md mandates the Tailwind class block on every form; flag any form missing the `__init__` widget.attrs application.
- **Dead URLs / unused views** — views or URL patterns that no template references after refactors.
- **Migration cleanliness** — multiple migration files for what should have been a single change; squash candidates.
- **N+1 query hotspots** — list views with `.all()` calls inside template loops over related objects.

Output format: a single triaged list grouped by severity (blocker / should-fix / nice-to-have) with file paths and line numbers, ready to be turned into discrete tickets. Do not fix during the sweep — fixes happen in follow-up sessions.

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

## queries — Query Client

### Overview

The queries app generates SQL; the query client is where users actually **run** it. It is a read-only execution surface for any query against a connected source:

- The natural-language-generated SQL produced by the queries app
- The starter SQL attached to generated use case suggestions (today these are display-only — see the `sources — Intra-Source Suggested Use Cases` section) and to cross-source agent insights
- Ad-hoc SQL a user writes or pastes themselves for that source
- Look at django-sql-explorer as an option for this

### Key Principle — Results Are Not Stored

Query results are **displayed only, never persisted**. Flint stores metadata and insights about data, not the data itself — that invariant holds here too. Results are rendered in a paginated table for the request and then discarded; no result rows are written to the Flint database. CSV export, if offered, is generated on the fly from the in-memory result set.

### Relationship to the Queries App

The query client shares the execution path defined in the queries app — `sqlglot` SELECT-only validation, the read-only database role, `statement_timeout`, and AST-enforced `LIMIT` (see the queries `Execution Safety Checklist`). It can ship as part of the queries app or as a thin follow-on: the queries app builds the generate-and-execute pipeline, and the query client generalizes the "execute" half so it works for any query source, not just LLM-generated ones.

Each execution is still logged (user, query, duration, row count) per the safety checklist — only the result rows are excluded from storage.

---

## catalog — ERD Generator / Viewer

### Overview

A visual entity-relationship diagram view generated from catalog metadata. Tables become nodes, foreign-key relationships become edges. Users can browse the structure of a source visually instead of clicking through the table list, which is especially useful for unfamiliar databases or for sharing schema context with stakeholders.

The ERD is a **derived view of the catalog** — it stores no extra data. Every node and edge is computed at view time from `Schema`, `Table`, `Column`, and the FK relationship records captured during sync. When the source schema changes and a re-sync runs, the diagram updates automatically.

This pairs naturally with the queries app: a user exploring "what's in this database?" can flip between the ERD (structural view) and the natural-language query box (analytical view) on the same source. 
Look at this for inspiration: https://github.com/royalbhati/sqltoerdiagram
---

### Where It Lives in the UI

A new **"Diagram"** tab on `sources/source_detail.html`, alongside the existing Overview, Schemas, and Insights tabs. The diagram occupies the full width of the content area below the tab nav.

Controls along the top of the diagram:

1. **Schema filter** — multi-select dropdown of all schemas in the source; default is "all"
2. **Search** — text input that highlights matching tables and dims the rest (does not remove edges, so neighbourhoods stay visible)
3. **Focus mode** — click a table to enter focus mode: show only that table and its direct neighbours (1-hop); click again or press Esc to exit
4. **Label mode** — toggle between **Physical** (raw `tbl_cust_master`) and **Business** (ontology-mapped "Customer") labels; Business mode is only available for tables that have an `ObjectType` defined (Phase 2 of `ontology`)
5. **Export** — download as PNG or SVG (Phase 3)

Each node displays:
- Table name (or business label, depending on mode)
- Schema badge (if multiple schemas are visible)
- Column list — primary keys marked with a key icon, FK columns with a link icon; collapsible if the table has more than ~10 columns
- Row count badge if `TableStatistics` exists for the table

Each edge displays:
- A line from the FK column on the source table to the PK column on the target table
- Cardinality indicator at the endpoints (`1`, `N`) — derived from whether the FK column has a unique constraint
- Hover tooltip with the FK constraint name and column pair

---

### How Generation Works

1. **Build graph data** — view queries `Schema`, `Table`, `Column`, and the FK relationship records (captured during sync — already required by the queries app for correct JOIN generation, so this dependency is shared) for the requested source, scoped to `request.account`. Apply the schema filter if provided.

2. **Serialize to JSON** — the view returns a JSON payload shaped for the rendering library:

   ```json
   {
     "nodes": [
       {
         "id": "schema.table",
         "label": "customers",
         "schema": "public",
         "columns": [
           {"name": "id", "type": "uuid", "is_pk": true},
           {"name": "email", "type": "varchar", "is_fk": false},
           {"name": "company_id", "type": "uuid", "is_fk": true}
         ],
         "row_count": 12453,
         "object_type": "Customer"
       }
     ],
     "edges": [
       {
         "from": "public.customers",
         "to": "public.companies",
         "from_column": "company_id",
         "to_column": "id",
         "cardinality": "many_to_one",
         "constraint_name": "customers_company_id_fkey"
       }
     ]
   }
   ```

3. **Client-side rendering** — `cytoscape.js` (preferred — better large-graph performance and built-in layout algorithms than `vis.js`) renders the graph in the browser. Use the `dagre` layout for hierarchical schemas (typical OLTP shape) with a fallback to `cose` (force-directed) for highly connected graphs. No server-side graph library required.

4. **Layout persistence (optional, Phase 2)** — if the user manually drags nodes, persist the positions per-user-per-source in a small `ERDLayout` model so the diagram opens in the same arrangement next time. Keyed by `(account, source, user)`.

---

### LLM-Inferred Relationships (Phase 3)

Many real-world databases have implicit relationships that aren't declared as FK constraints — common in legacy systems, data warehouses, or denormalized analytics tables. After explicit FKs are rendered, optionally run an **inferred-relationship pass**:

1. For each pair of tables in the source, check column-name and type compatibility (e.g., `orders.customer_id` matches `customers.id`)
2. For pairs with high name/type compatibility but no declared FK, ask the LLM to confirm whether this looks like a real relationship given the table descriptions and a sample of column names
3. Store accepted inferences in an `InferredRelationship` model with `confidence` and `reviewed_by_user` fields
4. Render inferred edges as **dashed lines** (vs. solid for declared FKs); user can accept/reject inline to confirm or hide

This reuses the LLM abstraction from `apps/insights/` — same provider layer, same prompt management. Cap LLM calls per source (e.g., max 20 candidate pairs per run) and rate-limit re-runs.

---

### Key Libraries

| Library | Purpose |
|---|---|
| `cytoscape.js` | Frontend graph rendering and layout (`dagre` extension for hierarchical layout) |
| existing LLM abstraction | Shared with `apps/insights/` — only used in Phase 3 for inferred relationships |
| existing catalog models | `Schema`, `Table`, `Column`, FK relationship records — no new sync work required for Phase 1 |

---

### Data Model

**Phase 1** — no new models. The view is fully derived from existing catalog data.

**Phase 2** — add `ERDLayout` for per-user layout persistence:

```
ERDLayout
  account     FK → accounts.Account
  source      FK → sources.Source
  user        FK → users.User
  positions   JSONField   {"schema.table": {"x": 120, "y": 340}, ...}
  updated_at  DateTimeField
```

**Phase 3** — add `InferredRelationship` for LLM-inferred edges:

```
InferredRelationship
  account             FK → accounts.Account
  source              FK → sources.Source
  from_table          FK → catalog.Table
  from_column         FK → catalog.Column
  to_table            FK → catalog.Table
  to_column           FK → catalog.Column
  confidence          CharField   high / medium / low
  reasoning           TextField   LLM reasoning
  status              CharField   suggested / accepted / rejected
  reviewed_by         FK → users.User (nullable)
  reviewed_at         DateTimeField (nullable)
  first_inferred_at   DateTimeField
```

---

### Phased Build

1. **Phase 1** — basic ERD per source from declared FK relationships only; cytoscape.js with dagre layout; schema filter and table search; physical labels only
2. **Phase 2** — focus mode (1-hop neighbourhood); ontology-aware business labels (when `ObjectType` exists for a table); per-user layout persistence via `ERDLayout`
3. **Phase 3** — LLM-inferred relationships rendered as dashed edges with accept/reject UI; PNG/SVG export

---

### Relationship to Existing Features

- **Builds on FK relationship capture during sync** — already a prerequisite for the queries app (correct JOIN generation). If queries ships first, this dependency is already satisfied.
- **Reuses ontology object/property names for cleaner labels** — when an `ObjectType` is defined for a table (Phase 1 of `ontology`), the ERD can show the business label instead of the physical table name. The ontology graph view (`/ontology/graph/`) and the ERD use the same rendering library and node/edge JSON shape — share the frontend code.
- **Reuses the LLM abstraction from `apps/insights/`** for the Phase 3 inferred-relationship pass — same provider layer, same prompt management pattern.
- **Lives in `apps/catalog/`** — a new view and template, plus optional models added in later phases. No new app needed.

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

---

## infrastructure — Tailwind CDN to Production Build

Currently using the Tailwind CDN play script (`<script src="https://cdn.tailwindcss.com">`). This is fine for development but not suitable for production — it's larger, slower, and doesn't support purging unused classes.

Before production deployment, replace the CDN script with a proper Tailwind build step:
1. Install Tailwind via npm: `npm install -D tailwindcss`
2. Create `tailwind.config.js` with the `content` paths pointing at all templates
3. Create a `static/css/input.css` with the Tailwind directives
4. Add a build script to `package.json` that outputs to `static/css/output.css`
5. Replace the CDN `<script>` in `base.html` with a `<link>` to the compiled stylesheet
6. Move the inline `tailwind.config` block from `base.html` into `tailwind.config.js`
