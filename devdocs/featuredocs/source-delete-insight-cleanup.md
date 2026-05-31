# Feature: Delete Source → Cascade-Clean Its Insights

**Source:** `devdocs/appdocs/post_mvp.md` — Suggested Build Order item 10f
**Status:** Implemented — signal passing `manage.py check` and manually verified via the UI (source-overview, use-case, and table-description insights all cleaned up on source delete; no orphaned `InsightTarget` rows). Automated tests deferred to the Phase 6 testing pass.
**Target phase:** Post-MVP Phase 3 (split from 10b, "Source Detail Updates")

---

## Overview

Deleting a `Source` currently orphans its insights. Catalog rows (`Schema`, `Table`, `Column`, `TableStatistics`) and sync rows `CASCADE` off `Source` at the DB level, but insights attach through the generic `InsightTarget` FK (`content_type` + `object_id`), which has **no** DB-level cascade. So when a source is deleted, its Source Overview and use-case-suggestion insights (which target the source) and its table-description insights (which target the source's tables) are left behind as orphaned rows. This feature adds a `pre_delete` signal on `Source` that deletes those `Insight` rows before the source and its catalog tables are removed.

---

## Dependencies

Everything required already exists — this is a small, self-contained cleanup.

- [x] `apps/sources/` — `Source` model and `apps/sources/signals.py` (already wired via `SourcesConfig.ready()`)
- [x] `apps/insights/` — `Insight` and `InsightTarget` models (generic FK via `content_type` + `object_id`)
- [x] `apps/catalog/` — `Schema` → `Table` relationship (`Table.schema.source`), used to collect the source's table PKs
- [x] `django.contrib.contenttypes` — `ContentType.objects.get_for_model()` to resolve the `Source` and `Table` content types

---

## Implementation Checklist

Single flat checklist — no phases.

#### Signals
- [x] Add a `pre_delete` receiver on `Source` in `apps/sources/signals.py` (alongside the existing `SourceSchedule` `post_delete` receiver), type-hinted per CLAUDE.md (`from __future__ import annotations`, annotated params and `-> None`). — `cleanup_insights_on_source_delete`
- [x] In the receiver, resolve `ContentType.objects.get_for_model(Source)` and `ContentType.objects.get_for_model(Table)`.
- [x] Collect the deleted source's `Table` PKs **before** deletion (e.g. `Table.objects.filter(schema__source=instance)`) — the tables cascade away with the source, so they must be gathered while they still exist. This is why `pre_delete` (not `post_delete`) is required. — done via an `object_id__in=Table.objects.filter(schema__source=instance)` subquery evaluated during the `pre_delete` filter.
- [x] Delete the targeted `Insight` rows: insights whose `InsightTarget` points at the source (`content_type=source_ct, object_id=instance.pk`) **and** insights whose `InsightTarget` points at any of the source's tables (`content_type=table_ct, object_id__in=table_pks`). Deleting the `Insight` rows cascades their `InsightTarget` rows (`InsightTarget.insight` is `on_delete=CASCADE`). — two-branch `Q(...) | Q(...)`, then `Insight.objects.filter(pk__in=...).delete()`.
- [x] Scope all queries by `account=instance.account` to respect tenancy.

#### Wiring
- [x] No new wiring needed — `apps/sources/signals.py` is already imported by `SourcesConfig.ready()`. Receiver lives in that already-imported module; `manage.py check` passes (imports resolve, no circular import).

#### Tests
Deferred to the Phase 6 testing pass — the six cases (source/table-targeted deletion, no orphaned `InsightTarget` rows, tenancy boundary, other-source insights left intact) are written up in `devdocs/testing.md` under `apps.sources` → "Source delete — insight cleanup". Verified manually in the shell for now.

---

## Key Design Decisions

- **`pre_delete`, not `post_delete`:** the source's `Table` rows cascade away when the source is deleted, so the table PKs needed to find table-targeted insights must be collected before deletion happens. A `post_delete` handler would run after the tables are already gone.
- **Delete `Insight`, let `InsightTarget` cascade:** `InsightTarget.insight` is `on_delete=CASCADE`, so deleting the `Insight` rows automatically removes their `InsightTarget` rows. Deleting only the `InsightTarget` rows would instead leave the `Insight` rows orphaned — the opposite of the goal.
- **Generic FK is the root cause:** insights attach via `content_type` + `object_id` rather than a real FK, which is why Django's normal FK cascade never fires here and a signal is required.
- **Two content types in scope:** source-targeted insights (`source_overview`, `use_case_suggestion`) use the `Source` content type; table-targeted insights (`table_description`) use the `Table` content type. Both must be handled.
- **Split from 10b** to keep the Source Detail Updates branch focused; discovered during that work.

---

## Notes

- The existing creation paths confirm the targeting shape this cleanup must reverse:
  - Source-targeted: `apps/insights/views.py` and `apps/sources/tasks.py` create `InsightTarget` with `content_type=ContentType.objects.get_for_model(Source)`, `object_id=source.pk`.
  - Table-targeted: `apps/insights/views.py:40` resolves a `Table` content type for `table_description` insights.
- Wrap the deletes in a single `transaction.atomic()` block if you want the cleanup and the source deletion to be all-or-nothing; Django already runs cascade deletes inside a transaction, and `pre_delete` fires within it, so this is largely covered — note it only if the reviewer flags atomicity.
- **Hard delete (decided):** the `Insight` rows are hard-deleted, not soft-flipped. The `Insight.status` enum includes a `'deleted'` choice, but it is intentionally not used here — orphaned insights for a deleted source have no value, so the rows are removed outright (which is what cascades the `InsightTarget` rows).