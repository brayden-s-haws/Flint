# Feature: Agentic Cross-Source Discovery

**Source:** `devdocs/appdocs/post_mvp.md` — "insights — Agentic Cross-Source Discovery" (build order item #11)
**Status:** Not started
**Target phase:** Post-MVP Phase 3 (after Celery + Redis, depends on 2+ sources connected)
**Suggested branch:** `feature/cross-source-discovery` (Phase 1) — already checked out

---

## Overview

A multi-step deterministic pipeline that proactively inspects all of an account's connected sources, discovers join opportunities and semantic overlaps between them, generates cross-source insight hypotheses, filters for quality and novelty, and surfaces the best ones as `Insight` records in the UI (and later via email digest). This is the cross-source counterpart to the intra-source "Suggested Uses" feature (`devdocs/featuredocs/intra-source-use-cases.md`): that surfaces what's possible *within* one source; this surfaces what's possible *across* two or more. Control flow is plain Python with LLM calls at specific steps (not a free-form ReAct loop), which keeps it debuggable and cost-controllable.

---

## Dependencies

- [x] `apps/insights/` LLM abstraction — `BaseService`, `get_service(provider)`, prompt modules under `apps/insights/prompts/`, and the `Insight` / `InsightTarget` / `InsightPrompt` models. This feature is additive to all of these.
- [x] `apps/insights/` `Insight.structured_data` JSONField — already exists; reused to store insight text + starter SQL (same approach as `use_case_suggestion`).
- [x] `apps/insights/` `InsightTarget` GenericForeignKey — links one insight to *two* `Source` rows (one `InsightTarget` per source).
- [x] Celery + Redis — `Flint/celery.py`, `apps/<app>/tasks.py` auto-discovery, worker + beat running. See `devdocs/featuredocs/celery-and-redis-setup.md`.
- [x] `django-celery-beat` DB scheduler — used for the Phase 3 weekly scheduled run. See `devdocs/featuredocs/scheduled-syncs.md`.
- [x] `apps/sources/signals.py` + `apps/sources/apps.py::ready()` — signal wiring pattern already established; the Phase 2 event trigger ("new source synced") hangs off this.
- [x] `apps/catalog/` `Schema`, `Table`, `Column` — the metadata reasoned over. DDL-summary reconstruction pattern already exists in `apps/insights/prompts/intra_source_use_cases.py::build_use_case_suggestions_prompt`.
- [x] 2+ sources connected and synced for an account (otherwise nothing to pair). Sync completion is detectable via `Source.first_synced_at` and `SourceSyncLog`.
- [ ] **Phase 3 only:** pgvector for embedding-based deduplication. Requires PostgreSQL (dev is currently SQLite — see Notes). Shared with the future queries-app embedding index.
- [ ] **Phase 3 only:** an embeddings call path (OpenAI/Anthropic embeddings) added to the service layer — does not exist yet.

---

## New App?

**Decision: no new app — build in `apps/insights/`.** The spec allows "a new `apps/agents/` app if scope warrants it," but the feature reuses the `Insight` model, `InsightTarget`, the provider layer, and the prompt-module convention. Adding it to `apps/insights/` mirrors how intra-source use cases were built. If the pipeline code grows unwieldy, a `apps/insights/agent/` sub-package (services + pipeline steps) is the refactor seam, not a new Django app. (Open question noted below.)

---

## Implementation Checklist

### Phase 1 — Manual trigger, single explicitly-selected source pair

End-to-end pipeline for one user-selected pair. No Step 2 scoring, no scheduling, no embeddings. Goal: validate prompt quality (Steps 3, 4, 6) and the review workflow (Step 7).

#### Models
- [x] Extend `Insight.insight_type` choices in `apps/insights/models.py` with `('cross_source_use_case', 'Cross Source Use Case')`. Migration generated + applied. *(Named `cross_source_use_case` — the cross-source twin of intra-source `use_case_suggestion` — not the spec's prose `cross_source_agent`. This featuredoc is authoritative for the literal string.)*
- [x] Extend `Insight.status` choices with `('pending_review', 'Pending Review')` and `('dismissed', 'Dismissed')` — agent insights land in `pending_review` and become `active` on accept, `dismissed` on dismiss. Migration generated + applied.
- [ ] No new `structured_data` shape change needed — store `{title, description, business_value, join_strategy, starter_sql, ...}` per the spec's Step 6 JSON. Confirm the render template reads from `structured_data`, not `text`. *(Deferred to the storage + template steps — nothing to do at the model layer.)*

#### Pipeline (services)
- [x] `apps/insights/prompts/cross_source_discovery.py` — new prompt module mirroring `intra_source_use_cases.py`. Contains:
  - `RELATIONSHIP_DISCOVERY_SYSTEM_MESSAGE`, model constant(s), max-tokens constant, `build_relationship_discovery_prompt(source_a, source_b, join_key_candidates=None)` — emits the Step 3 JSON (`join_opportunities`, `semantic_overlaps`). DDL summary per source built via shared `_build_ddl_summary` helper; per-source overview context via `_get_source_overview_text` (correctly filtered, optional). `join_key_candidates` reserved for Phase 2 (unused in Phase 1).
  - `HYPOTHESIS_SYSTEM_MESSAGE` + `build_hypothesis_prompt(relationship, source_a, source_b)` — emits the Step 4 JSON (`hypotheses` with `title`, `description`, `business_value`, `join_strategy`, `required_data`, `specificity_score`). Renders the relationship via `json.dumps` (shape-agnostic across join-opportunity / semantic-overlap) **plus the full DDL of both sources** so hypotheses are grounded in real columns (anti-hallucination — validated in shell that this drives `required_data` to 100% real columns).
  - `CROSS_SOURCE_INSIGHT_SYSTEM_MESSAGE` + `build_cross_source_insight_prompt(hypothesis, source_a, source_b)` — emits the Step 6 full insight (`title`, `description`, `business_value`, `starter_sql`). Also receives both sources' DDL so the starter SQL references only real tables/columns. The system message includes a SQL-validity guard (e.g. don't put a window function like NTILE inside `GROUP BY`) — prompts reduce but can't guarantee valid SQL; the starter query is display-only until the queries app's `sqlglot` validation. Models: cheaper tier (`gpt-5.4-mini` / `claude-haiku-4-5`) for Steps 3 & 4; better tier (`gpt-5.4` / `claude-sonnet-4-6`) for the Step 6 user-facing write.
  - **Note for the pipeline:** Steps 4 and 6 both take `source_a, source_b` (not just the relationship/hypothesis) — `run_discovery_for_pair` must thread the two `Source` objects through to every builder, not only Step 3.
- [ ] Add three abstract methods to `BaseService` (`apps/insights/services/base.py`), signatures matching the prompt builders (Steps 4 and 6 take the sources too, so hypotheses/insights stay schema-grounded): `discover_cross_source_relationships(source_a: Source, source_b: Source) -> list[dict]` (returns `join_opportunities` — or the full Step 3 dict; decide and keep consistent across providers), `generate_cross_source_hypotheses(relationship: dict, source_a: Source, source_b: Source) -> list[dict]`, `generate_cross_source_insight(hypothesis: dict, source_a: Source, source_b: Source) -> dict`.
- [ ] Implement all three in **both** `anthropic_service.py` and `openai_service.py`. Use the cheaper model for discovery/hypothesis, the better model for the final insight write (per "Cost and Quality Controls").
  - **Code-fence stripping is required, not optional (confirmed in shell).** The models return the JSON wrapped in a ```​json fence despite the "return only valid JSON" system message — `json.loads` on the raw text will raise. Each method must strip the fence before parsing, exactly as `generate_intra_source_use_case` does: if the response starts with ```` ``` ````, drop the first line and the trailing fence, then `json.loads`. Verified against `claude-haiku-4-5` during the prompt-validation pass (HubSpot + Customer Database demo pair).
  - Each method then pulls the top-level key from the parsed object: Step 3 → `join_opportunities` / `semantic_overlaps`, Step 4 → `hypotheses`, Step 6 → the full insight dict.
  - This fence-strip + `json.loads` + key-extract dance repeats 3× per provider (6× total). If it gets copy-heavy, factor a small `_parse_json_response(raw)` helper — but let the duplication appear first before abstracting.
- [ ] `apps/insights/pipeline.py` (or `apps/insights/agent/pipeline.py`) — orchestration function `run_discovery_for_pair(source_a, source_b, run) -> int` that calls Step 3 → Step 4 → (Phase 1: no Step 5 dedup) → Step 6 → Step 7 and returns insights-created count. Plain Python; LLM calls via `get_service(...)`.
  - **Phase 1 fan-out policy (decided):** Step 3 yields many relationships and Step 4 yields 3–5 hypotheses each, so the pipeline must cap. Take the top ~2–3 relationships by `confidence`, run Step 4 on those, pool all hypotheses, **sort by the `specificity_score` each hypothesis already carries, and take the top 5** — Step 6 writes one insight per survivor (≈5 insights per pair). This is the embedding-free Phase 1 version of Step 5's "surface at most N, ranked" rule; the cap (N=5) matches the spec. Phase 3's Step 5 adds *dedup* (pgvector) on top of this ranking — no rework. Keeps the expensive Sonnet Step-6 calls bounded at 5/pair.

#### Storage (Step 7)
- [ ] For each surviving hypothesis create one `Insight(insight_type='cross_source_use_case', status='pending_review', structured_data=...)` and **two** `InsightTarget` rows (one per source, GenericFK to `Source`), all scoped to `source.account`.

#### Views & URLs (`apps/insights/`)
- [ ] `run_cross_source_discovery` — `POST /insights/discovery/run/` — accepts two `source_id`s (the explicitly chosen pair), validates both belong to `request.account` and are synced, enqueues the pipeline Celery task. Rate-limited to once / 24h (mirror the `generate_intra_use_case_suggestions` guard). Returns the review-section partial.
- [ ] `cross_source_discovery_status` — `GET /insights/discovery/status/` — HTMX poll endpoint that renders the review section (spinner while running, cards when ready), matching the async-on-first-view pattern in `devdocs/featuredocs/async-table-descriptions.md`.
- [ ] `accept_agent_insight` — `POST /insights/<insight_id>/accept/` — flips `pending_review` → `active`, swaps the card row (HTMX).
- [ ] `dismiss_agent_insight` — `POST /insights/<insight_id>/dismiss/` — flips → `dismissed`, swaps the card row.
- [ ] All views `@login_required` and scope every queryset by `account=request.account`.
- [ ] Add the URL patterns to `apps/insights/urls.py` under `app_name = 'insights'`.

#### Celery
- [ ] `run_cross_source_discovery_task(account_id, source_a_id, source_b_id)` in `apps/insights/tasks.py` — IDs only (per `CLAUDE.md` Celery rule). Loads objects, calls the pipeline, marks the `AgentInsightRun` (created in Phase 2; Phase 1 may pass `run=None`) complete/failed. Catch + log exceptions like the existing tasks.

#### Templates
- [ ] `insights/_cross_source_discovery.html` — the discovery section: pair selector (two `<select>` of the account's synced sources), "Run discovery" button, spinner state, and the result cards.
- [ ] `insights/_agent_insight_card.html` — one card: title, description, business value, tables-involved badges, collapsible starter SQL (`<details>`), Accept / Dismiss buttons. Reuse the intra-source use-case card styling.
- [ ] Dashboard card — add a **"Discovered Insights"** card to `templates/core/dashboard.html` next to the existing Insights card (per the post_mvp note "add this to the dashboard as one of the main cards next to the Insights card"). Extend `apps/core/views.py::DashboardView.get_context_data` with a `pending_review` agent-insight count.

#### Tests
- [ ] Pipeline produces `Insight` + 2 `InsightTarget` rows for a pair (mock the LLM service).
- [ ] Accept/dismiss transitions status correctly and are account-scoped.
- [ ] Discovery run is rejected (400) when rate-limited or when a source isn't synced / belongs to another account (tenancy boundary).

---

### Phase 2 — Multi-pair with Step 2 scoring, event-triggered

#### Models
- [ ] Add `category` to `apps/sources/models.py::SourceType` — `CharField` with choices `crm / analytics / database / ecommerce / support` (nullable/blank for unknown). Backs the Step 2 cross-domain matrix. Migration + admin registration. (Does not exist today — `SourceType` has only `name` and `is_demo`.)
- [ ] `AgentInsightRun` (new model, `apps/insights/models.py`, extends `TenantAwareModel`) — fields per spec: `status` (running/completed/failed/partial), `started_at`, `completed_at` (nullable), `sources_analyzed`, `pairs_evaluated`, `hypotheses_generated`, `insights_created`, `error_log` (TextField), `triggered_by` (schedule/new_source/manual). Migration + admin.
- [ ] `CrossSourceRelationship` (new model, `apps/insights/models.py`, extends `TenantAwareModel`) — `source_a`/`source_b` FKs to `sources.Source`, `source_a_table`/`source_a_column`/`source_b_table`/`source_b_column` CharFields, `join_type` (direct/fuzzy/temporal), `confidence` (high/medium/low), `reasoning` TextField, `first_discovered`, `last_confirmed`, `is_active` BooleanField. Migration + admin.

#### Pipeline
- [ ] Step 1 — `gather_source_inventory(account)` returns synced sources grouped by `SourceType.category`, with table/column metadata and sync recency.
- [ ] Step 2 — `score_source_pair(source_a, source_b) -> float` deterministic pre-filter combining: (1) known cross-domain matrix on `category`, (2) shared normalized column-name fingerprints (lowercase, strip underscores/camelCase — `email`/`user_id`/`*_id`/date families), (3) temporal overlap (both have date-typed columns). No LLM calls. Only pairs above a threshold advance.
- [ ] Cache Step 3 — persist results as `CrossSourceRelationship`; reuse across runs; only re-run Step 3 for a pair when new tables/columns were synced since `last_confirmed`. Set `is_active=False` when a referenced source/column no longer exists.
- [ ] Cap LLM calls per run (e.g. 10); prioritize highest-scoring pairs; log when the cap is hit. Update `AgentInsightRun` counters as the run progresses.

#### Triggering
- [ ] Event trigger — when a source finishes its **first** successful sync (extend the completion path in `apps/sources/tasks.py::sync_source_task`, or add a signal), enqueue the full account pipeline if the account now has 2+ synced sources. `triggered_by='new_source'`.
- [ ] Manual full-account run — extend the Phase 1 button to also offer "Run discovery across all sources" (not just one pair), rate-limited to once / 24h. `triggered_by='manual'`.

#### Tests
- [ ] Pair scoring: known-domain pair and shared-join-key pair both score above threshold; unrelated pair scores below.
- [ ] `CrossSourceRelationship` is reused (not re-discovered) when no new catalog rows since `last_confirmed`.
- [ ] New-source sync on an account with one prior synced source fires exactly one pipeline run.

---

### Phase 3 — Scheduled runs + embedding deduplication

#### Scheduling
- [ ] Celery beat periodic task running the pipeline weekly for every eligible account (2+ synced sources, last `AgentInsightRun` > 6 days ago). `triggered_by='schedule'`. Use the `django-celery-beat` DB scheduler already configured.

#### Deduplication (Step 5)
- [ ] pgvector enabled (requires Postgres — see Notes). Embed each new hypothesis's title+description; embed/lookup existing account `Insight`s; cosine similarity > ~0.85 → skip as already-known. Reuses the embedding index intended for the queries app.
- [ ] Quality filter (Step 5, can land earlier): discard hypotheses with `specificity_score < 0.6`, generic vapid-phrase titles, or `required_data` columns that don't exist in `catalog.Column`.
- [ ] Per-run rate cap: surface at most N new insights/account/run (e.g. 5), ranked by specificity + pair novelty.

#### Dismissed-insight feedback
- [ ] Persist the dismissed signal so the same pattern isn't resurfaced (e.g. store a fingerprint of dismissed hypotheses and skip near-matches on later runs).

#### Tests
- [ ] Near-duplicate hypothesis (high cosine similarity to an existing insight) is skipped.
- [ ] Hypothesis referencing a non-existent column is discarded by the quality filter.
- [ ] Scheduled run skips accounts whose last run was < 6 days ago.

---

### Phase 4 — Email digest + quality iteration

- [ ] Weekly plain-text email digest ("We found N new opportunities across your connected sources") via Django's email system.
- [ ] Use accumulated accept/dismiss signals to tune Step 2 pair-scoring weights and model/prompt selection.

---

### Phase 5 (future, not scoped) — Multi-source combinations (3+ sources)

Generalize Step 3 onward from a *pair* to a *combination* of sources (N labelled DDL blocks; multi-hop join chains A↔B↔C). Deferred until two-source discovery proves its value — the combinatorial blow-up (k-subsets of N sources grow far faster than pairs) makes Step 2 pre-filtering and the per-run LLM-call cap load-bearing. **Keep the `source_a`/`source_b` signatures through Phase 4; only generalize to `list[Source]` when this phase is picked up.** See `post_mvp.md` agentic "Phased Build" item 5 for the full rationale.

---

## Key Design Decisions

- **Deterministic pipeline, not an agent loop.** Control flow is Python; LLM calls happen at named steps (3, 4, 6). This is an explicit spec decision for debuggability and cost control. Don't refactor into a free-form ReAct agent.
- **Reuse `Insight` + `InsightTarget`, not new insight tables.** Cross-source insights are `insight_type='cross_source_use_case'` with two `InsightTarget` rows (GenericFK to both `Source`s) and the structured payload in `structured_data` — exactly the pattern intra-source use cases established. Starter SQL lives in `structured_data`, never parsed out of prose.
- **`pending_review` status + review queue.** Agent insights are surfaced for accept/dismiss before becoming `active`, at least initially — the agent is proactive and unprompted, so a human gate protects insight-list quality.
- **Pre-filter aggressively before spending tokens (Step 2).** Pair scoring is deterministic and LLM-free; only high-scoring pairs reach Step 3. Cap LLM calls per run and use cheaper models for discovery/hypothesis, the better model only for the final insight.
- **`CrossSourceRelationship` is a cache.** Discovered joins persist and are reused across runs; Step 3 only re-runs for pairs with new catalog rows. This is the main cost lever for scheduled runs.
- **Cost scales with source *pairs*, not tables.** 3 sources = 3 pairs, 5 sources = 10 pairs. Keep the per-run LLM cap in mind as accounts grow.
- **`apps/insights/prompts/intra_source_use_cases.py` is the starting point.** The DDL-summary builder and JSON-output structure are nearly identical; the difference is feeding two sources' schemas instead of one.

---

## Notes

- **`last_synced_at` vs. reality:** the spec's Step 1 references `last_synced_at`, but `Source` has no such field — it has `first_synced_at` (set on first successful sync). The app already *derives* "last synced" the same way in two places: `SourceListView` annotates `last_synced_at=Max('sourcesynclog__completed_at')` (`apps/sources/views.py:41`) and `SourceDetailView` reads the latest `status='success'` `SourceSyncLog` (`:124`). Step 1 should reuse the `Max('sourcesynclog__completed_at')` annotation pattern for recency and `first_synced_at` for "has it ever synced." Don't add a `last_synced_at` model field.
- **`SourceType.category` does not exist yet** — it's a Phase 2 model addition. Phase 1 works on an explicitly chosen pair, so it doesn't need categories.
- **pgvector requires PostgreSQL.** Dev is currently SQLite (`db.sqlite3`). Phase 3 deduplication assumes the Postgres + pgvector move is done (it's also a queries-app prerequisite). **Confirmed plan:** stand up Postgres when Phase 3 starts — at that point Claude will provide step-by-step setup instructions (install Postgres + the pgvector extension, create the dev DB/role, point `DATABASE_URL` at it, migrate, enable the `vector` extension, swap the dev `DATABASES` engine). Until then Phase 1/2 stay on SQLite.
- **No embeddings call path exists** in the service layer today; Phase 3 adds one. The current `BaseService` only does text completions.
- **Package layout (decided):** built in `apps/insights/` — no `apps/agents/` app. If `pipeline.py` + the three prompt builders + services grow large, extract to an `apps/insights/agent/` sub-package rather than a new Django app. Note: the natural-language-to-SQL "queries" feature (post_mvp item #15) is currently scoped as its own `apps/queries/` app in `post_mvp.md`; that's a separate decision and doesn't change where cross-source discovery lives. If you also want queries folded into `apps/insights/`, that's a `post_mvp.md` edit to make when that feature comes up — flag it then.
- **Destructive-sequence caution:** unlike the intra-source regenerate flow (which deletes existing suggestions *before* the LLM call — flagged in the post_mvp bug-bash list), the agent pipeline should create new `pending_review` insights without deleting prior ones up front; dedup (Phase 3) handles overlap. Don't repeat the delete-before-LLM pattern here.
- **Security:** credentials are never needed by this pipeline — it reasons over catalog metadata only, never connects to source DBs. The starter SQL is display-only until the queries app exists.
- **Benefits from ontology + queries apps** (later phases): ontology object types would let the agent reason about "Customer" rather than `tbl_cust_master`; the queries app turns the display-only starter SQL into runnable seed queries. Neither is a hard dependency.