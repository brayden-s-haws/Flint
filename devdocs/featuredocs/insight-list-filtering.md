# Feature: Insight List Filtering and Search

**Source:** `devdocs/appdocs/post_mvp.md` — insights section
**Status:** Complete
**Target phase:** Post-MVP Phase 1

---

## Overview

The MVP insight list shows all insights for an account with no way to filter or search. This feature adds filtering by insight type (e.g. table description, source overview) and by source/table target, plus text search across insight content. All filters are implemented as URL query params — no JavaScript required.

---

## Dependencies

- [x] `apps/insights/` — `Insight`, `InsightTarget`, and `InsightListView` must all be in place
- [x] `apps/sources/` — `Source` model needed for source filter options
- [x] `apps/catalog/` — `Table` model needed for table filter options

---

## Implementation Checklist

#### Views & URLs
- [x] `InsightListView.get_queryset()` — extend to read `?type=<insight_type>`, `?source=<source_pk>`, and `?q=<search_term>` from `self.request.GET` and filter accordingly:
  - `q` filters on `insight.text__icontains`
  - `type` filters on `insight.insight_type`
  - `source` filters via `InsightTarget` OR query: insights targeting the source directly, plus insights targeting any table belonging to that source; tenant-scoped
- [x] `InsightListView.get_context_data()` — passes `q`, `selected_insight_type`, `selected_source`, distinct `insight_types`, and tenant-scoped `sources`

#### Templates
- [x] `insights/insight_list.html` — filter/search bar added with text input, insight type dropdown, source dropdown, Filter button, and Clear link

---

## Key Design Decisions

- **URL query params, no JavaScript:** Same approach as source list filtering — server-side, bookmarkable, no HTMX needed.
- **`icontains` for text search:** Search across `insight.text` for substring matches.
- **Distinct insight types for dropdown:** Rather than hardcoding type values, query the database for types that actually exist. This keeps the dropdown accurate as new insight types are added.

---

## Notes

- `insight_type` values currently in use: `'ai'` (auto-generated) and potentially others — check the `Insight` model's field definition for the full list of choices.
- Source filtering joins through `InsightTarget` using `ContentType`. You'll need to import `ContentType` from `django.contrib.contenttypes.models` and `Source` from `apps.sources.models` in `views.py`. The `source` query param should be the source PK (integer), so cast it with `int()` before filtering — or use `get_object_or_404` to be safe.