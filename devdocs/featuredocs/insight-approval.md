# Feature: Insight Approval/Rating

**Source:** `devdocs/appdocs/post_mvp.md` — "Insight approval/rating — thumbs up/down workflow so users can accept or reject generated insights"
**Status:** Not started
**Target phase:** Post-MVP Phase 2

---

## Overview

Add a thumbs up/down rating mechanism to insights so users can accept or reject LLM-generated content. This provides a lightweight feedback signal: accepted insights are trusted, rejected ones are flagged for review or regeneration. The rating lives directly on the `Insight` model as a simple field — no separate model needed for this scope.

---

## Dependencies

- [x] `apps/insights/` — `Insight` model exists with `status` and `text` fields
- [x] `InsightTarget` — links insights to sources/tables via `GenericForeignKey`
- [x] `insight_detail.html` and `insight_list.html` — existing templates where rating UI will appear

---

## Implementation Checklist

### Model Change
- [x] Add `rating` field to `Insight` model — `CharField` with choices: `('none', 'None'), ('approved', 'Approved'), ('rejected', 'Rejected')`, default `'none'`
- [x] Run `makemigrations` and `migrate`

### View
- [x] Add `rate_insight` view in `apps/insights/views.py` — `POST /insights/<int:pk>/rate/`:
  - Accepts a `rating` parameter from the POST body (`approved` or `rejected`)
  - Validates the rating value is one of the allowed choices
  - Updates `insight.rating` and saves
  - Returns an HTMX partial response (the updated rating buttons) so the UI updates in place without a full page reload
  - Requires login (`@login_required`) and verifies `insight.account == request.account`

### URL
- [x] Add URL in `apps/insights/urls.py`: `path('<int:pk>/rate/', views.rate_insight, name='rate')`

### Template — Rating Partial
- [x] Create `templates/insights/_rating_buttons.html` — a small partial containing:
  - Thumbs up button — highlighted (e.g., `text-flint-success`) when `insight.rating == 'approved'`, muted otherwise
  - Thumbs down button — highlighted (e.g., `text-red-400`) when `insight.rating == 'rejected'`, muted otherwise
  - Both buttons use `hx-post` to `{% url 'insights:rate' insight.pk %}` with a hidden input or `hx-vals` to send the rating value
  - `hx-target` points to the rating buttons container so just the buttons swap on click
  - `hx-swap="outerHTML"` so the partial replaces itself

### Template — Insight Detail Page
- [x] Add the rating buttons partial (`{% include 'insights/_rating_buttons.html' %}`) to `insight_detail.html`, inside the first card below the description text
- [x] Wrap the include in a `<div id="rating-{{ insight.pk }}">` so HTMX can target it

### Template — Insight List Page
- [x] Add the rating buttons partial to each insight row/card in `insight_list.html`
- [x] Each instance needs a unique `id="rating-{{ insight.pk }}"` wrapper

### Template — Source Detail Page (use case cards)
- [x] Add rating buttons to each use case card in `source_detail.html` within the Suggested Use Cases section
- [x] Pass each use case's `Insight` object (not just `structured_data`) to the template so the rating partial has access to `insight.pk` and `insight.rating`

---

## Key Design Decisions

- **Field on `Insight`, not a separate model:** A simple `rating` field on `Insight` is sufficient for thumbs up/down. A separate `InsightRating` model would only be needed if multiple users could rate the same insight independently (multi-user rating is a Phase 5 concern).
- **`'none'` default, not `null`:** Using a string default avoids null-handling complexity in templates and queries. `'none'` means "not yet rated."
- **HTMX partial swap:** The rating buttons are a standalone partial so the same component works on the detail page, list page, and source detail page. HTMX swaps just the buttons — no full page reload needed.
- **Toggling behavior:** Clicking the same rating again should reset to `'none'` (un-rate). Clicking the opposite rating switches it. Handle this logic in the view.

---

## Notes

- For the thumbs up/down icons, use simple Unicode characters (e.g., `&#9650;` / `&#9660;` or `&#128077;` / `&#128078;`) or SVG icons. No icon library needed for two icons.
- The `source_detail.html` use case section currently passes `use_case.structured_data` dicts to the template. To add rating buttons there, the view context will need to pass the `Insight` objects (or at minimum the `pk` and `rating` alongside each `structured_data` dict).
- The `rate_insight` view should return the `_rating_buttons.html` partial directly (using `render()` with just the partial template), not redirect. This is what makes the HTMX swap work.