# Bug Bash — Running Punch List

A running list of bugs, dead code, and cleanup items found *during* feature development, to be triaged and fixed in the Phase 6 bug-bash pass (`devdocs/appdocs/post_mvp.md` item #26).

**Find, don't fix.** Items are logged here as they're noticed so they don't derail in-flight feature work. Fixes happen in dedicated follow-up sessions after feature work is complete — see the ordering note in `post_mvp.md` Phase 6.

Triaged by severity: **blocker** / **should-fix** / **nice-to-have**. Each item lists file paths and line numbers so it can be turned into a discrete ticket.

> The `post_mvp.md` "## bug bash" section lists the *categories* to sweep for at bash time. This file is the accumulating list of concrete items found early.

---

## nice-to-have

### 1. Source-overview lookup is duplicated across three call sites

The "get the active Source Overview insight text for a source" query is implemented in three places:

- `apps/insights/views.py:79-84` (`build_use_cases_context`)
- `apps/insights/prompts/intra_source_use_cases.py:33-41` (`build_use_case_suggestions_prompt`)
- `apps/insights/prompts/cross_source_discovery.py` (`_get_source_overview`)

All three now filter correctly (by source + `insight__insight_type='source_overview'`, returning text only when `status == 'active'`), but the logic is copied three times.

**Fix:** centralize into one reusable query (e.g. a manager method `Insight.objects.get_source_overview(source) -> str | None`, or a helper in `apps/insights/`) and point all three call sites at it. Found during the cross-source discovery build (post_mvp item #11).

> **Correctness bug already fixed (2026-06-04):** the `intra_source_use_cases.py` copy previously omitted the `insight_type` filter and the `status == 'active'` check, so it could feed the wrong insight's text (or empty/pending text) into the use-case prompt. Fixed inline during the item #11 build; only the dedup refactor remains.

---

### 2. DDL-summary builder is duplicated across prompt modules

The schema → table → column loop that reconstructs `CREATE TABLE` statements from catalog models exists in two prompt modules:

- `apps/insights/prompts/intra_source_use_cases.py:22-30` (inline in `build_use_case_suggestions_prompt`)
- `apps/insights/prompts/cross_source_discovery.py` (`_build_ddl_summary`)

**Fix:** extract a single shared helper (e.g. `apps/insights/prompts/_ddl.py`, or a method closer to the `catalog` models) and have both prompt modules call it. Low risk — pure formatting, no behavior change. Deferred deliberately mid-feature to avoid coupling the two prompt modules during active work. Found during the cross-source discovery build (post_mvp item #11).

> Note: if richer DDL is ever wanted (primary keys, foreign keys, nullability) for better join detection, make that improvement *in the shared helper* so both intra-source and cross-source prompts benefit — don't fork it.

---

### 3. Cross-source prompt builders: duplicated dual-schema block + repeated DDL recompute

Within `apps/insights/prompts/cross_source_discovery.py`, two related cleanups deferred during the item #11 build:

- **DRY:** `build_hypothesis_prompt` and `build_cross_source_insight_prompt` build the identical labelled two-source block (`Source A: "{name}" (type) / {ddl}` + `Source B: ...`). Extract a `_build_dual_schema_block(source_a, source_b) -> str` helper both call. (`build_relationship_discovery_prompt` can't share it — it interleaves the optional source overviews between the two schemas, so its layout differs.)
- **Perf:** `_build_ddl_summary` re-queries the catalog on every call, and the three builders each call it. In the real pipeline, Step 4 runs once per relationship and Step 6 once per hypothesis, so each source's DDL is rebuilt many times per pair. Build each source's DDL/schema block **once per pair** in `run_discovery_for_pair` and reuse it (or memoize `_build_ddl_summary` by `source.pk`). Negligible at Phase 1 scale (manual, single pair); revisit when the pipeline fans out across many relationships/pairs (Phase 2+).

**Fix:** both deferred deliberately — keeping the builders self-contained (take a `Source`, build their own DDL) kept them independently shell-testable during the build. Found during the cross-source discovery build (post_mvp item #11).