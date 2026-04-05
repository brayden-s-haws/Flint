# Feature: Source List Filtering and Search

**Source:** `devdocs/appdocs/post_mvp.md` — sources section
**Status:** Complete
**Target phase:** Post-MVP Phase 1

---

## Overview

The MVP source list shows all sources for an account with no way to filter or search. This feature adds a source type filter and a text search so users can quickly find sources by name. Both are implemented as URL query params processed in the view — no JavaScript required.

---

## Dependencies

- [x] `apps/sources/` — `Source` and `SourceType` models, `SourceListView`, and `source_list.html` must all be in place

---

## Implementation Checklist

#### Views & URLs
- [x] `SourceListView.get_queryset()` — extend to read `?type=<source_type_name>` and `?q=<search_term>` from `self.request.GET` and filter the queryset accordingly; `q` filters on `name__icontains` and `source_type__name__icontains`; `type` filters on `source_type__name`
- [x] `SourceListView.get_context_data()` — passes `q`, `source_type`, and `source_types` (all `SourceType` objects) to the template

#### Templates
- [x] `sources/source_list.html` — add a filter/search bar above the source list containing:
  - A text input for name search bound to the `q` query param
  - A `<select>` dropdown for source type bound to the `type` query param, populated from `SourceType` objects (pass them in context from the view)
  - A submit button to apply filters; form uses `method="get"` with no `action` so it submits to the current URL
  - A "Clear" link that resets to `/sources/` with no params

---

## Key Design Decisions

- **URL query params, no JavaScript:** Filters are applied server-side via `GET` params. The form submits normally — no HTMX or JS needed. This keeps the implementation simple and makes filtered views bookmarkable/shareable.
- **`icontains` for name search:** Case-insensitive substring match on `source.name` — consistent with how Django search is typically implemented.
- **Filter by `source_type__name`:** Use the string name (e.g. `postgresql`) rather than a numeric PK in the URL so params are human-readable.

---

## Notes

- The `SourceType` queryset for the dropdown should be scoped to types that the current account actually has sources for — or just all `SourceType` objects. Either works at this scale; all types is simpler.
- Open question: should filtering preserve existing annotations (e.g. `last_synced_at`)? Yes — the filter should chain on top of the existing `get_queryset()` logic, not replace it.