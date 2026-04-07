# Feature: Catalog Table List Filtering and Search

**Source:** `devdocs/appdocs/post_mvp.md` — catalog section
**Status:** Complete
**Target phase:** Post-MVP Phase 1

**Note:** The post_mvp.md entry describes filtering by source or schema. The developer has scoped this to filtering by source and searching by table name.

---

## Overview

The MVP table list shows all tables across all sources for an account with no way to filter or search. This feature adds a source filter and a table name text search so users can quickly find what they're looking for. Both are implemented as URL query params processed in the view — no JavaScript required.

---

## Dependencies

- [x] `apps/catalog/` — `Table`, `Schema` models and `TableListView` must be in place
- [x] `apps/sources/` — `Source` model needed to populate the source filter dropdown

---

## Implementation Checklist

#### Views & URLs
- [x] `TableListView.get_queryset()` — extend to read `?source=<source_pk>` and `?q=<search_term>` from `self.request.GET` and filter accordingly:
  - `q` filters on `table.name__icontains`
  - `source` filters on `schema__source_id=source_pk`; tenant-scoped with `schema__source__account=self.request.account`
- [x] `TableListView.get_context_data()` — passes `q`, `selected_source`, and tenant-scoped `sources` (`Source.objects.filter(account=self.request.account)`)

#### Templates
- [x] `catalog/table_list.html` — filter/search bar added with text input, source dropdown, Filter button, and Clear link

---

## Key Design Decisions

- **URL query params, no JavaScript:** Same approach as source and insight list filtering — server-side, bookmarkable.
- **Filter by source PK:** Source PKs are used as the dropdown value (integers in the URL), consistent with how the insight list source filter works.
- **Tenant scoping:** Both the `source` filter queryset and the sources dropdown must be scoped to `self.request.account` to prevent cross-account data leakage.

---

## Notes

- `TableListView.get_queryset()` currently chains `.select_related('schema', 'schema__source')` — the new filters should chain on top of this, not replace it.
- `Source` is not currently imported in `apps/catalog/views.py` — you'll need to add `from apps.sources.models import Source`.