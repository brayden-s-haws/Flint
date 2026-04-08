# Feature: Table Statistics

**Source:** `devdocs/appdocs/post_mvp.md` — catalog section; `devdocs/architecture.md` — Phase 2 roadmap  
**Status:** In progress  
**Target phase:** Post-MVP Phase 2

---

## Overview

Table Statistics captures a snapshot of quantitative metadata for each table at sync time — row counts, column null rates, distinct value counts, and common values. This data is stored in a `TableStatistics` model (planned in `devdocs/architecture.md` but not yet implemented), surfaced on the table detail page, and later used as LLM context for SQL generation and insight quality. It's the observability layer that turns Flint from a schema catalog into a data intelligence platform.

---

## Dependencies

- [x] `apps/catalog/` — `Table` and `Column` models exist and are populated by sync
- [x] `apps/sources/connectors/postgresql.py` — `get_table_metadata` already fetches `row_count` via `pg_class`; this feature extends that pattern
- [x] `apps/sources/views.py` — `sync_source` already calls `get_table_metadata` per table; statistics collection hooks into the same sync flow
- [ ] No Celery required for Phase 1 (sync is already synchronous); Celery would be needed for a standalone "refresh statistics" background task in a later phase

---

## Implementation Checklist

### Phase 1 — Model & Sync Collection

#### Models
- [x] `TableStatistics` in `apps/catalog/models.py` — one record per table per sync; key fields:
  - `table` — FK to `Table` (CASCADE)
  - `account` — FK (inherit `TenantAwareModel`)
  - `row_count` — `BigIntegerField(null=True)` — total rows at snapshot time
  - `synced_at` — uses inherited `created_at` from `TenantAwareModel`
  - `column_stats` — `JSONField(default=dict)` — per-column stats keyed by column name; each entry contains:
    - `null_fraction` — float 0.0–1.0 (nulls / total rows)
    - `distinct_count` — integer (approx or exact)
    - `common_values` — list of up to 5 most frequent values (strings)

#### Connector Changes
- [ ] Extend `get_table_metadata` return type in `apps/sources/connectors/base.py` to include `column_stats: dict` alongside `row_count`
- [ ] Implement column statistics query in `apps/sources/connectors/postgresql.py` — query `pg_stats` (populated by `ANALYZE`) for `null_frac`, `n_distinct`, and `most_common_vals` per column; fall back to `None` if `pg_stats` has no data for the table yet
  - SQL: `SELECT attname, null_frac, n_distinct, most_common_vals FROM pg_stats WHERE schemaname = %s AND tablename = %s`

#### Sync Wiring
- [ ] In `apps/sources/views.py` `sync_source`, after saving `table.row_count`, create a `TableStatistics` record from the expanded `get_table_metadata` result
  - Use `TableStatistics.objects.create(...)` — always create a new snapshot; do not `update_or_create`; old snapshots are historical records
  - Pass `account=source.account`, `table=table`, `row_count=metadata['row_count']`, `column_stats=metadata.get('column_stats', {})`

#### Migrations
- [x] Run `makemigrations catalog` to generate the migration for `TableStatistics`

#### Tests
- [ ] Test that `sync_source` creates a `TableStatistics` record for each table after a successful sync
- [ ] Test that `PostgreSQLConnector.get_table_metadata` returns `column_stats` as a dict (can be empty if `pg_stats` has no rows)
- [ ] Test `TableStatistics` model str/repr and field defaults

---

### Phase 2 — UI Display on Table Detail

#### Views
- [ ] In `apps/catalog/views.py` `TableDetailView.get_context_data`, fetch the most recent `TableStatistics` for the table:
  - `TableStatistics.objects.filter(table=self.object).order_by('-synced_at').first()`
  - Add to context as `context['statistics']` (may be `None` if no sync has run yet)

#### Templates
- [ ] `templates/catalog/table_detail.html` — add a "Statistics" section below the columns list:
  - Show `row_count` as a formatted number (e.g., `1,234,567`)
  - Show `synced_at` as a relative or absolute timestamp (e.g., "Last updated 3 hours ago")
  - If `column_stats` is populated, render a small table with columns: Column Name | Null Rate | Distinct Values | Common Values
  - Show an empty state ("No statistics available — run a sync to collect them") when `statistics` is `None`

---

### Phase 3 — LLM Context Injection

> **Note:** This phase is explicitly called out in `devdocs/appdocs/post_mvp.md` under "Natural Language to SQL — Integration with Catalog". It is a dependency for the SQL generation feature, not a standalone UI feature.

#### Connector / Service Changes
- [ ] In the LLM insight service (`apps/insights/services/`), when building the table context for prompt injection, include the most recent `TableStatistics.column_stats` for the table
  - Inject `null_fraction`, `distinct_count`, and `common_values` as inline DDL comments on the relevant `CREATE TABLE` block
  - Example: `-- null_rate: 0.12, distinct: 847, common: ['US', 'CA', 'GB']`
- [ ] Only inject stats if `synced_at` is within the last 7 days (stale stats are misleading)

#### Tests
- [ ] Test that the prompt builder includes column stats when a recent `TableStatistics` record exists
- [ ] Test that stats older than 7 days are excluded from prompt injection

---

## Key Design Decisions

- **Snapshot not update:** Each sync creates a new `TableStatistics` row rather than overwriting the previous one. This preserves history for trend detection (row count over time) and is consistent with `SourceSyncLog` being an append-only log.
- **`pg_stats` not live count:** The PostgreSQL connector uses `pg_stats` (which reads `ANALYZE` output) for column-level stats rather than running live `COUNT(*)` or `COUNT(DISTINCT ...)` queries per column. This is much faster and avoids locking, but requires that `ANALYZE` has run on the target database. The `row_count` already uses `pg_class.reltuples` for the same reason.
- **JSONField for column stats:** Column stats are stored in a single `JSONField` keyed by column name rather than a separate `ColumnStatistics` model. This avoids a large number of rows (one per column per sync) and is sufficient for the LLM context use case. If columnar trend analysis becomes a requirement, a separate model could be introduced later.
- **No Celery in Phase 1:** Statistics are collected inline during the existing sync flow, keeping the implementation simple. A dedicated "Refresh Statistics" button that runs as a background task can be added when Celery is introduced.

---

## Notes

- `pg_stats` is only populated after PostgreSQL runs `ANALYZE` on the table. Freshly created tables or tables that have never been vacuumed will return no rows. The connector must handle this gracefully (return empty dict, not error).
- `most_common_vals` in `pg_stats` is a PostgreSQL array stored as a string (e.g., `{US,CA,GB}`). The connector needs to parse this into a Python list before storing.
- `n_distinct` in `pg_stats` can be negative (PostgreSQL stores it as a fraction of total rows when negative, e.g., `-0.5` means ~50% distinct). Convert: if `n_distinct < 0`, compute `abs(n_distinct) * row_count` for a concrete estimate.
- For non-PostgreSQL sources (future), `get_table_metadata` can simply return `column_stats: {}` — the `TableStatistics` record will still be created with an empty dict.
- Open question: Should old `TableStatistics` records be pruned automatically? No policy defined in source docs — leave all history for now.