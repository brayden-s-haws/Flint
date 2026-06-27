# Feature: Agentic Cross-Source Discovery

**Source:** `devdocs/appdocs/post_mvp.md` — "insights — Agentic Cross-Source Discovery" (build order item #11)
**Status:** Phase 1 in progress — models + prompt module + service layer + pipeline (incl. storage) + Celery task done and verified; views/URLs → templates → dashboard card → tests remain
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
- [x] No new `structured_data` shape change needed at the model layer — `Insight.structured_data` JSONField already exists; the Step 6 payload (`{title, description, business_value, join_strategy, starter_sql, ...}`) stores as-is. *(The "does the template read it correctly" verification moved to the Templates section, where it's actually satisfied.)*

#### Pipeline (services)
- [x] `apps/insights/prompts/cross_source_discovery.py` — new prompt module mirroring `intra_source_use_cases.py`. Contains:
  - `RELATIONSHIP_DISCOVERY_SYSTEM_MESSAGE`, model constant(s), max-tokens constant, `build_relationship_discovery_prompt(source_a, source_b, join_key_candidates=None)` — emits the Step 3 JSON (`join_opportunities`, `semantic_overlaps`). DDL summary per source built via shared `_build_ddl_summary` helper; per-source overview context via `_get_source_overview_text` (correctly filtered, optional). `join_key_candidates` reserved for Phase 2 (unused in Phase 1).
  - `HYPOTHESIS_SYSTEM_MESSAGE` + `build_hypothesis_prompt(relationship, source_a, source_b)` — emits the Step 4 JSON (`hypotheses` with `title`, `description`, `business_value`, `join_strategy`, `required_data`, `specificity_score`). Renders the relationship via `json.dumps` (shape-agnostic across join-opportunity / semantic-overlap) **plus the full DDL of both sources** so hypotheses are grounded in real columns (anti-hallucination — validated in shell that this drives `required_data` to 100% real columns).
  - `CROSS_SOURCE_USE_CASE_SYSTEM_MESSAGE` + `build_cross_source_use_case_prompt(hypothesis, source_a, source_b)` — emits the Step 6 full insight (`title`, `description`, `business_value`, `starter_sql`). Also receives both sources' DDL so the starter SQL references only real tables/columns. *(Step 6 constants/builder share the `CROSS_SOURCE_USE_CASE` stem so they line up with the `generate_cross_source_use_case` method name.)* The system message includes a SQL-validity guard (e.g. don't put a window function like NTILE inside `GROUP BY`) — prompts reduce but can't guarantee valid SQL; the starter query is display-only until the queries app's `sqlglot` validation. Models: cheaper tier (`gpt-5.4-mini` / `claude-haiku-4-5`) for Steps 3 & 4; better tier (`gpt-5.4` / `claude-sonnet-4-6`) for the Step 6 user-facing write.
  - **Note for the pipeline:** Steps 4 and 6 both take `source_a, source_b` (not just the relationship/hypothesis) — `run_discovery_for_pair` must thread the two `Source` objects through to every builder, not only Step 3.
- [x] Add three abstract methods to `BaseService` (`apps/insights/services/base.py`), signatures matching the prompt builders (Steps 4 and 6 take the sources too, so hypotheses/insights stay schema-grounded): `discover_cross_source_relationships(source_a: Source, source_b: Source) -> dict` (**returns the full Step 3 dict** — `{join_opportunities, semantic_overlaps}`; the pipeline owns flatten/rank, decided), `generate_cross_source_hypotheses(relationship: dict, source_a: Source, source_b: Source) -> list[dict]`, `generate_cross_source_use_case(hypothesis: dict, source_a: Source, source_b: Source) -> dict`.
- [x] Implement all three in **both** `anthropic_service.py` and `openai_service.py`. Cheaper model for discovery/hypothesis, better model for the final insight write (per "Cost and Quality Controls"). Verified via `manage.py shell` that both classes satisfy `BaseService` (`__abstractmethods__` empty) and import cleanly.
  - **Code-fence stripping is required, not optional (confirmed in shell).** The models return the JSON wrapped in a ```​json fence despite the "return only valid JSON" system message — `json.loads` on the raw text will raise. Each method must strip the fence before parsing, exactly as `generate_intra_source_use_case` does: if the response starts with ```` ``` ````, drop the first line and the trailing fence, then `json.loads`. Verified against `claude-haiku-4-5` during the prompt-validation pass (HubSpot + Customer Database demo pair).
  - Return shapes (decided, consistent across providers): Step 3 → the **full parsed dict** (`{join_opportunities, semantic_overlaps}` — both lists kept; pipeline flattens/ranks), Step 4 → `result['hypotheses']`, Step 6 → the full insight dict. Only Step 4 unwraps a key (it has a single top-level `hypotheses`); Steps 3 and 6 return the object whole.
  - This fence-strip + `json.loads` + key-extract dance repeats 3× per provider (6× total). If it gets copy-heavy, factor a small `_parse_json_response(raw)` helper — but let the duplication appear first before abstracting.
- [x] `apps/insights/cross_source_pipeline.py` — orchestration function `run_discovery_for_pair(source_a, source_b, run) -> int` that calls Step 3 → Step 4 → (Phase 1: no Step 5 dedup) → Step 6 → Step 7 and returns insights-created count. Plain Python; LLM calls via `get_service(...)`. Verified end-to-end in shell with a mocked service (see sub-bullets).
  - [x] `_flatten_and_rank_relationships(relationship) -> list[dict]` — pure helper that merges Step 3's `join_opportunities` + `semantic_overlaps` into one ranked list. Confidence maps high/medium/low → 3/2/1 (`CONFIDENCE_RANK`), unknown/missing confidence degrades to 0, semantic overlaps rank below all joins (`SEMANTIC_OVERLAP_RANK = 0`). Uses a `_rank` scratch key for the sort, stripped before return so it never reaches Step 4's `json.dumps`. Both keys read via `.get(..., [])` to survive a missing list. Verified in shell (ordering, scratch-key cleanup on output *and* input, missing-key guard, junk-confidence guard).
  - [x] `run_discovery_for_pair(...)` orchestration body — Step 3 → flatten/rank → cap top 5 relationships → Step 4 fan-out + pool → sort pooled by `specificity_score` (missing/None coerced to `0.0`) → top 5 → Step 6 → store. Per-item `try/except` (`except Exception` + `logger.exception` + `continue`) around Step 4 and Step 6+store so one bad item doesn't sink the run; Step 3 left bare (a Step 3 failure has nothing to isolate and propagates to the task). Returns the count of insights actually persisted (increment sits *after* a successful store).
  - [x] `_store_cross_source_use_case(use_case_data, source_a, source_b) -> Insight` — **(renamed from the spec's `_store_cross_source_insight` to line up with `generate_cross_source_use_case`)** non-destructive create (one `Insight`, two `InsightTarget` rows, `status='pending_review'`), wrapped in `transaction.atomic()` so an insight is never left with fewer than its two targets.
  - **Shell-verified end-to-end (mocked service, rolled back in a transaction):** return value = 4 insights, `+4` Insight rows, `+8` InsightTarget rows (2/insight), Step 4 called once per ranked relationship, Step 6 once per surviving hypothesis, every row `status='pending_review'` / `insight_type='cross_source_use_case'` / two `source` targets / correct `account`. A hypothesis with a missing `specificity_score` did not crash the sort (coerced to 0.0). Rollback left zero residue in the dev DB.
  - **Phase 1 fan-out policy (decided):** Step 3 yields many relationships and Step 4 yields 3–5 hypotheses each, so the pipeline must cap. Take the top **5 relationships** by rank (`merged[:5]`), run Step 4 on those, pool all hypotheses, **sort by the `specificity_score` each hypothesis already carries, and take the top 5** — Step 6 writes one insight per survivor (≈5 insights per pair). This is the embedding-free Phase 1 version of Step 5's "surface at most N, ranked" rule; the final cap (N=5 hypotheses) matches the spec. Phase 3's Step 5 adds *dedup* (pgvector) on top of this ranking — no rework. Keeps the expensive Sonnet Step-6 calls bounded at 5/pair. *(The relationship-level cap is 5 for now; it can tighten to ~2–3 later if Step 4 volume/cost warrants — the final hypothesis cap is what bounds the expensive Step 6.)*

#### Storage (Step 7)
- [x] For each surviving hypothesis create one `Insight(insight_type='cross_source_use_case', status='pending_review', structured_data=...)` and **two** `InsightTarget` rows (one per source, GenericFK to `Source`), all scoped to `source.account`. Implemented as `_store_cross_source_use_case` in `cross_source_pipeline.py` (renamed from the spec's `_store_cross_source_insight`); shell-verified (+1 Insight / +2 InsightTarget per call, correct status/type/account).
- [x] **Regeneration is non-destructive (decided).** Re-running discovery for a pair (or account) must **not** delete prior `cross_source_use_case` insights. New insights are simply added; the pipeline has no delete step. Insights are displayed newest-first (`order_by('-created_at')`), so a re-run appends to the top and the history of past suggestions is preserved. This is the opposite of the current intra-source regenerate flow (which deletes first — see the destructive-sequence note) and is the behavior the intra-source rework (post_mvp item 11b) will adopt too. *(Confirmed in code: `_store_cross_source_use_case` has no delete; only `objects.create` calls.)*

#### Views & URLs (`apps/insights/`)
- [x] `CrossSourceDiscoveryView` — `GET /insights/discovery/` — **dedicated page** (not just a dashboard card or a section embedded elsewhere). Lists all `cross_source_use_case` insights for the account **newest-first** (`order_by('-created_at')`), with the pair selector + "Run discovery" trigger at the top. Because it's its own page, it's fine to display many insights at once (no scroll cap needed — contrast the intra-source card, item 11b, which is space-constrained and needs a scroll container). `LoginRequiredMixin` + account-scoped queryset. *(Implemented in `apps/insights/views.py`: `get_queryset` filters `insight_type='cross_source_use_case'`, prefetches `insighttarget_set`, orders newest-first; `get_context_data` passes synced sources + filter values. URL pattern still TODO.)*
  - [x] **Filtering + search (same approach as `catalog` and `insights` list pages).** URL query params processed in `get_queryset`, no JavaScript: `?source=<id>` filters to insights linked to that source (match **either** of the two `InsightTarget` sources, since each cross-source insight links two), and `?q=<text>` searches insight content (title/description in `structured_data`, and/or `text`). Mirror the param handling in `InsightListView.get_queryset` (`apps/insights/views.py`) — including the `ContentType`/`InsightTarget` source-filter pattern already used there. Pass the account's sources + current filter values into context for the filter controls, same as the existing list pages. *(Done: `?source` filters on `insighttarget__content_type`/`object_id` with `.distinct()`; `?q` does `text__icontains`. `get_context_data` exposes `sources` (filtered to `first_synced_at__isnull=False`), `q`, `selected_source`.)*
- [ ] `run_cross_source_discovery` — `POST /insights/discovery/run/` — accepts two `source_id`s (the explicitly chosen pair), validates both belong to `request.account` and are synced, enqueues the pipeline Celery task. Rate-limited to once / 24h (mirror the `generate_intra_use_case_suggestions` guard). **Appends** new insights (non-destructive — never deletes prior ones). Returns the results-section partial.
- [ ] `cross_source_discovery_status` — `GET /insights/discovery/status/` — HTMX poll endpoint that renders the results section (spinner while running, then the newest-first list with new insights at the top), matching the async-on-first-view pattern in `devdocs/featuredocs/async-table-descriptions.md`.
- [ ] `accept_agent_insight` — `POST /insights/<insight_id>/accept/` — flips `pending_review` → `active`, swaps the card row (HTMX).
- [ ] `dismiss_agent_insight` — `POST /insights/<insight_id>/dismiss/` — flips → `dismissed`, swaps the card row.
- [ ] All views `@login_required` and scope every queryset by `account=request.account`.
- [ ] Add the URL patterns to `apps/insights/urls.py` under `app_name = 'insights'`.

#### Celery
- [x] `run_cross_source_discovery_task(account_id, source_a_id, source_b_id)` in `apps/insights/tasks.py` — IDs only (per `CLAUDE.md` Celery rule). Loads both `Source`s **scoped to `account_id`** (`Source.objects.get(pk=..., account_id=account_id)` — tenancy guard, last line of defense behind the view), calls `run_discovery_for_pair` with `run=None` (Phase 1), logs the insights-created count on success. Whole-run `try/except` (`logger.exception`) — the pipeline already isolates per-item failures internally, and since it creates many `pending_review` insights there's no single row to mark failed, so the task just logs. Verified the module imports and the task registers with Celery. *(Phase 2 hook noted in code: create an `AgentInsightRun`, thread `run=` through, mark complete/failed here.)*

#### Templates
- [ ] `insights/cross_source_discovery.html` — the **dedicated page** (extends `base.html`). Top: pair selector (two `<select>` of the account's synced sources) + "Run discovery" button, and the filter/search controls (source `<select>` + search `<input>` as a GET form, styled like the catalog/insights list pages). Below: the newest-first list of insight cards. Includes the results-section partial for HTMX swap during a run.
- [ ] `insights/_cross_source_discovery_results.html` — the results section partial (spinner state during a run, then the newest-first card list with new insights at the top). Swapped in by the status poll endpoint.
- [ ] `insights/_agent_insight_card.html` — one card: title, description, business value, tables-involved badges, collapsible starter SQL (`<details>`), Accept / Dismiss buttons. Reuse the intra-source use-case card styling.
  - **Confirm the card reads from `structured_data`, not `text`** — render `insight.structured_data.title` / `.description` / `.business_value` / `.starter_sql` (the Step 6 payload), since cross-source insights store their content in `structured_data`. *(Moved here from #Models — this is where the no-shape-change decision actually gets verified.)*
- [ ] Dashboard card — add a fourth **stat card** to the top card row in `templates/core/dashboard.html`, alongside the existing **Sources**, **Tables**, and **Insights** cards (e.g. "Cross-Source Insights"). The card shows a count and **links to the dedicated page** (`GET /insights/discovery/`). Extend `apps/core/views.py::DashboardView.get_context_data` with the count (e.g. `cross_source_insight_count` — total `cross_source_use_case` insights for the account, or `pending_review` only; pick one and label the card accordingly).

#### Tests
- [ ] Pipeline produces `Insight` + 2 `InsightTarget` rows for a pair (mock the LLM service).
- [ ] Accept/dismiss transitions status correctly and are account-scoped.
- [ ] Discovery run is rejected (400) when rate-limited or when a source isn't synced / belongs to another account (tenancy boundary).

---

### Phase 2 — Multi-pair with Step 2 scoring, event-triggered

#### Models
- [ ] `AgentInsightRun` (new model, `apps/insights/models.py`, extends `TenantAwareModel`) — fields per spec: `status` (running/completed/failed/partial), `started_at`, `completed_at` (nullable), `sources_analyzed`, `pairs_evaluated`, `hypotheses_generated`, `insights_created`, `error_log` (TextField), `triggered_by` (schedule/new_source/manual). Migration + admin.
- [ ] `CrossSourceRelationship` (new model, `apps/insights/models.py`, extends `TenantAwareModel`) — `source_a`/`source_b` FKs to `sources.Source`, `source_a_table`/`source_a_column`/`source_b_table`/`source_b_column` CharFields, `join_type` (direct/fuzzy/temporal), `confidence` (high/medium/low), `reasoning` TextField, `first_discovered`, `last_confirmed`, `is_active` BooleanField. Migration + admin.

#### Pipeline
- [ ] Step 1 — `gather_source_inventory(account)` returns the account's synced sources with table/column metadata and sync recency. (No `SourceType.category` grouping — see the "no source-type bias" decision below.)
- [ ] Step 2 — `score_source_pair(source_a, source_b) -> float` deterministic, **structural-only** ranker (no LLM calls, no source-type prior). Combines: (1) shared normalized column-name fingerprints (lowercase, strip underscores/camelCase — `email`/`user_id`/`*_id`/date families), (2) temporal overlap (both have date-typed columns). Used to **order** pairs for spending the per-run LLM cap, **not** as a hard gate — at typical scale (2–5 sources = 1–10 pairs) run Step 3 on every pair up to the cap, highest-fingerprint-score first. Deliberately does **not** weight pairs by whether their source types "should" relate — that bias is what would suppress the surprising cross-domain insights this feature exists to find.
- [ ] Cache Step 3 — persist results as `CrossSourceRelationship`; reuse across runs; only re-run Step 3 for a pair when new tables/columns were synced since `last_confirmed`. Set `is_active=False` when a referenced source/column no longer exists.
- [ ] Cap LLM calls per run (e.g. 10); prioritize highest-scoring pairs (by the structural score above); log when the cap is hit. Update `AgentInsightRun` counters as the run progresses. **The per-run cap — not a category threshold — is the cost lever.**

#### Triggering
- [ ] Event trigger — when a source finishes its **first** successful sync (extend the completion path in `apps/sources/tasks.py::sync_source_task`, or add a signal), enqueue the full account pipeline if the account now has 2+ synced sources. `triggered_by='new_source'`.
- [ ] Manual full-account run — extend the Phase 1 button to also offer "Run discovery across all sources" (not just one pair), rate-limited to once / 24h. `triggered_by='manual'`.

#### Tests
- [ ] Pair scoring: a pair sharing join-key fingerprints (e.g. both have `email`/`*_id`) scores above a pair with no shared fingerprints and no temporal overlap. Scoring is order-only, so assert relative ordering, not a fixed threshold.
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

### Out of scope (tracked elsewhere)

These were originally sketched as later phases but are **not** part of shipping cross-source discovery. They live as backlog items, not build steps:

- **Email digest + feedback-driven quality iteration** — moved to `devdocs/potential_features.md` (Advanced Intelligence). Covers a weekly plain-text "We found N new opportunities across your connected sources" email, and using accumulated accept/dismiss signals to tune pair-scoring weights and model/prompt selection. Build later only if there's demand.
- **Multi-source combinations (3+ sources)** — generalize Step 3 onward from a *pair* to a *combination* of sources (N labelled DDL blocks; multi-hop join chains A↔B↔C). Deferred until two-source discovery proves its value — the combinatorial blow-up (k-subsets of N sources grow far faster than pairs) makes Step 2 pre-filtering and the per-run LLM-call cap load-bearing. **Keep the `source_a`/`source_b` signatures through Phase 3; only generalize to `list[Source]` if/when this is picked up.** Full rationale in `post_mvp.md` agentic "Phased Build" item 5.

---

## Key Design Decisions

- **Deterministic pipeline, not an agent loop.** Control flow is Python; LLM calls happen at named steps (3, 4, 6). This is an explicit spec decision for debuggability and cost control. Don't refactor into a free-form ReAct agent.
- **Reuse `Insight` + `InsightTarget`, not new insight tables.** Cross-source insights are `insight_type='cross_source_use_case'` with two `InsightTarget` rows (GenericFK to both `Source`s) and the structured payload in `structured_data` — exactly the pattern intra-source use cases established. Starter SQL lives in `structured_data`, never parsed out of prose.
- **`pending_review` status + review queue.** Agent insights are surfaced for accept/dismiss before becoming `active`, at least initially — the agent is proactive and unprompted, so a human gate protects insight-list quality.
- **Non-destructive regeneration.** Re-running discovery never deletes prior insights — it appends, and the list renders newest-first so re-runs stack on top with full history preserved. The pipeline has no delete step. This is a deliberate departure from the original intra-source regenerate flow (delete-then-generate, which both risks leaving the user with nothing on a failed LLM call *and* throws away past suggestions) and is the model the intra-source rework (post_mvp item 11b) will follow. Lives on a **dedicated page** (`/insights/discovery/`) with source filter + search, reached from a dashboard stat card alongside Sources/Tables/Insights.
- **Rank, don't gate, before spending tokens (Step 2).** Pair scoring is deterministic and LLM-free, used to *order* which pairs get the per-run LLM budget — not to hard-exclude pairs. Cap LLM calls per run and use cheaper models for discovery/hypothesis, the better model only for the final insight.
- **No source-type bias in pairing (decided — reversal of the original spec).** Step 2 scoring is *structural only* — shared column-name fingerprints + temporal overlap — with **no `SourceType.category` cross-domain matrix**. A category prior ("CRM joins with analytics") would bake in exactly the assumption that suppresses the surprising cross-domain insights this feature exists to surface, and it's largely redundant with the fingerprint signal (same-domain sources already share `contact`/`email`/`*_id` columns). The `SourceType.category` field was dropped from Phase 2 entirely — no new model field, migration, admin, or hand-maintained matrix. Fully reversible: if structural scoring under-filters at high source counts, add category *then*, informed by real data. The fuzzy/semantic matching a category prior might have caught is already Step 3's (the LLM's) job; Step 2 only decides spend order.
- **`CrossSourceRelationship` is a cache.** Discovered joins persist and are reused across runs; Step 3 only re-runs for pairs with new catalog rows. This is the main cost lever for scheduled runs.
- **Cost scales with source *pairs*, not tables.** 3 sources = 3 pairs, 5 sources = 10 pairs. Keep the per-run LLM cap in mind as accounts grow.
- **`apps/insights/prompts/intra_source_use_cases.py` is the starting point.** The DDL-summary builder and JSON-output structure are nearly identical; the difference is feeding two sources' schemas instead of one.

---

## Notes

- **`last_synced_at` vs. reality:** the spec's Step 1 references `last_synced_at`, but `Source` has no such field — it has `first_synced_at` (set on first successful sync). The app already *derives* "last synced" the same way in two places: `SourceListView` annotates `last_synced_at=Max('sourcesynclog__completed_at')` (`apps/sources/views.py:41`) and `SourceDetailView` reads the latest `status='success'` `SourceSyncLog` (`:124`). Step 1 should reuse the `Max('sourcesynclog__completed_at')` annotation pattern for recency and `first_synced_at` for "has it ever synced." Don't add a `last_synced_at` model field.
- **`SourceType.category` is intentionally not used** — the original spec proposed adding a `category` field to drive a Step 2 cross-domain matrix; that was dropped (see "No source-type bias in pairing" above). Step 2 scores pairs on structure (shared column fingerprints + temporal overlap), not on declared source type, so no `category` field is added in any phase.
- **pgvector requires PostgreSQL.** Dev is currently SQLite (`db.sqlite3`). Phase 3 deduplication assumes the Postgres + pgvector move is done (it's also a queries-app prerequisite). **Confirmed plan:** stand up Postgres when Phase 3 starts — at that point Claude will provide step-by-step setup instructions (install Postgres + the pgvector extension, create the dev DB/role, point `DATABASE_URL` at it, migrate, enable the `vector` extension, swap the dev `DATABASES` engine). Until then Phase 1/2 stay on SQLite.
- **No embeddings call path exists** in the service layer today; Phase 3 adds one. The current `BaseService` only does text completions.
- **Package layout (decided):** built in `apps/insights/` — no `apps/agents/` app. If `cross_source_pipeline.py` + the three prompt builders + services grow large, extract to an `apps/insights/agent/` sub-package rather than a new Django app. Note: the natural-language-to-SQL "queries" feature (post_mvp item #15) is currently scoped as its own `apps/queries/` app in `post_mvp.md`; that's a separate decision and doesn't change where cross-source discovery lives. If you also want queries folded into `apps/insights/`, that's a `post_mvp.md` edit to make when that feature comes up — flag it then.
- **Destructive-sequence caution:** unlike the intra-source regenerate flow (which deletes existing suggestions *before* the LLM call — flagged in the post_mvp bug-bash list), the agent pipeline should create new `pending_review` insights without deleting prior ones up front; dedup (Phase 3) handles overlap. Don't repeat the delete-before-LLM pattern here.
- **Security:** credentials are never needed by this pipeline — it reasons over catalog metadata only, never connects to source DBs. The starter SQL is display-only until the queries app exists.
- **Benefits from ontology + queries apps** (later phases): ontology object types would let the agent reason about "Customer" rather than `tbl_cust_master`; the queries app turns the display-only starter SQL into runnable seed queries. Neither is a hard dependency.