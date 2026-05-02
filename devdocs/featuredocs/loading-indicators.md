# Feature: Loading Indicators

**Source:** `devdocs/appdocs/post_mvp.md` — "Loading indicators for source sync and use case generation"
**Status:** In progress (Phase A complete)
**Target phase:** Post-MVP Phase 2 (item #5)
**Branch:** `feature/loading-indicators`

---

## Overview

Several actions in the app trigger long-running synchronous work — most notably source sync (catalog discovery + an LLM source-overview call inside the request cycle) and use case generation (LLM call). Today the user clicks a button and gets no feedback until the page reloads or the HTMX swap completes. On real PostgreSQL sources the sync can hang the browser for 20–60 seconds with nothing visible happening.

The goal of this feature is a single, reusable loading indicator pattern that:

- Disables the triggering button while a request is in flight (no double-submits).
- Shows an inline spinner next to (or replacing) the button label.
- Optionally shows a "working on it" message in the target area being replaced.
- Works the same way across HTMX and non-HTMX flows by converting the remaining non-HTMX flows to HTMX.

Scope is the four user-initiated POSTs listed in the checklist below. We are not adding indicators to navigation, list filters, or rating buttons (those return in <100ms and the latency isn't perceptible).

---

## Dependencies

- [x] HTMX 2.0.8 already loaded in `templates/base.html`
- [x] Tailwind CDN with `flint` color palette already configured
- [x] `_use_cases_section.html` already uses HTMX (`hx-post`/`hx-target`/`hx-swap`)

The sync, test connection, and load demo views currently return `redirect(...)`. Detecting `HX-Request` and returning a partial is part of the per-phase work (C/D/E), not a separate upfront step.

---

## Out of Scope

- **No async/Celery work in this feature.** Sync stays synchronous in the request cycle. Once Celery lands (post_mvp item #7) the sync spinner will evolve into a polling indicator that watches `SourceSyncLog.status`. Design the markup so that swap is mechanical: the button posts to the same URL, but the response becomes "started" + a poller. Don't pre-build the polling now.
- **No global "page is loading" overlay.** All indicators are local to the action that triggered them.
- **No skeleton placeholders.** Spinner + "Working…" text is sufficient for current load times.
- **No HTMX boost / full-page progress bar.** Per-action indicators only.

---

## Implementation Checklist

### Phase A — Reusable spinner component ✅

- [x] Create `templates/components/_spinner.html` — a small inline SVG spinner (animated via Tailwind's `animate-spin`) that renders nothing visually until its parent has the HTMX request class. Accepts an optional `label` template variable (default: "Working…") so callers can customise the text.
- [x] The spinner element carries both `htmx-indicator` (HTMX's hide/show hook) and `spinner` (so parent forms can resolve it via `hx-indicator="find .spinner"`).
- [x] No new CSS — `htmx-indicator` opacity rules ship with HTMX; rotation comes from Tailwind's `animate-spin`.
- [x] SVG uses `h-4 w-4` and `stroke="currentColor"` so the spinner inherits the surrounding text colour (works on both orange and muted-text backgrounds without per-use colour overrides).
- [x] Verified: include renders invisibly by default (DOM present, opacity 0). Will become visible only when paired with `hx-indicator` in Phase B onward.

### Phase B — Use case generation indicator (smallest, validates the pattern)

`templates/sources/_use_cases_section.html` already uses HTMX. Wire the spinner in.

- [ ] On both `<form>` elements (Generate and Regenerate, lines 8 and 33), add:
  - `hx-disabled-elt="find button"` — disables the submit button while in flight
  - `hx-indicator="find .spinner"` — points at the spinner element inside the form
- [ ] Inside each form, after the `<button>`, render `{% include 'components/_spinner.html' with label="Generating…" %}` wrapped in a span with class `spinner` so `find .spinner` resolves.
- [ ] Verify visually: clicking Generate disables the button, swaps in the spinner, and on response the section is replaced (existing behaviour — the spinner disappears with the swap).
- [ ] Verify error path: when `generate_intra_use_case_suggestions` returns a 400/500 (e.g. rate-limited or LLM failure), HTMX by default does NOT swap. The spinner stops, button re-enables, but the user sees no message. Decide: either let HTMX swap on 4xx/5xx for these specific endpoints (`hx-target-error` or response header), or render the error message as a partial. Recommend the latter — return the section template with an error banner appended for non-200 responses.

### Phase C — Source sync indicator (convert to HTMX)

`templates/sources/source_detail.html:13-16` — plain form POST, full page reload.

- [ ] Wrap the action buttons row in an identifiable container (e.g. `<div id="source-actions" class="flex gap-2">`) so we have a swap target for the sync result if needed.
- [ ] Convert the Sync Now form to HTMX:
  - `hx-post="{% url 'sources:sync' source.pk %}"` on the form
  - `hx-target="#sync-result"` (a new, initially-empty container placed below the actions row)
  - `hx-swap="innerHTML"`
  - `hx-disabled-elt="find button"`
  - `hx-indicator="find .spinner"`
- [ ] Add the spinner span inside the form button area, and add a sibling `<div id="sync-result"></div>` below the actions div.
- [ ] Update `sync_source` view in `apps/sources/views.py:155` to detect HTMX requests via `request.headers.get('HX-Request') == 'true'`. When HTMX:
  - On success: return a small partial that shows a success message and triggers a full page refresh via the `HX-Refresh: true` response header (this is the simplest correct behaviour — sync touches schemas/tables/sync history/source overview, all of which are different cards on the page; refreshing is cheaper than partial-rendering 4 sections)
  - On failure: return a partial with the error message rendered into `#sync-result`
- [ ] Confirm the existing non-HTMX path still works (in case anyone POSTs without HTMX — e.g. a curl test). The view should fall back to the existing `redirect('sources:detail', pk=pk)` path.
- [ ] **Important UX note:** the LLM source-overview generation runs after the sync DB writes (`apps/sources/views.py:204-211`), inside the same request. Sync requests therefore can take a long time on first sync. The spinner correctly reflects this — but consider adding a "Generating insights…" message swap halfway through. Out of scope for this feature; flag it for the Celery migration.

### Phase D — Test Connection indicator

`templates/sources/source_detail.html:17-20` — same pattern as sync, much shorter request.

- [ ] Convert Test Connection form to HTMX:
  - `hx-post="{% url 'sources:test_connection' source.pk %}"`
  - `hx-target="#test-connection-result"` (new sibling container near the button, or reuse `#sync-result`)
  - `hx-swap="innerHTML"`
  - `hx-disabled-elt="find button"`
  - `hx-indicator="find .spinner"`
- [ ] Add the spinner span inside the button area.
- [ ] Update `test_connection` view in `apps/sources/views.py:140` to detect HTMX and return a small partial with a green success or red error message inline, instead of using `messages` framework (which only shows on full reload).

### Phase E — Load Demo Data indicator (optional bundle)

`templates/sources/source_list.html` — load demo button. The action is local-only (no LLM), but can take a few seconds because it creates three sources and runs sync on each.

- [ ] Same pattern as Phase C: convert the form to HTMX, add spinner with label "Loading demo data…", target a result container, return `HX-Refresh: true` on success.
- [ ] If this turns out to be trivially fast in practice, ship it without a spinner and remove the checkbox. Validate timing first.

---

## Reusable Pattern (the "shape" to follow)

Every triggering form ends up looking like this (pseudocode):

```html
<form hx-post="..."
      hx-target="#some-result"
      hx-swap="innerHTML"
      hx-disabled-elt="find button"
      hx-indicator="find .spinner">
    {% csrf_token %}
    <button type="submit" class="bg-flint-orange ...">
        Action Label
        <span class="spinner inline-flex items-center gap-2">
            {% include 'components/_spinner.html' with label="Working…" %}
        </span>
    </button>
</form>
<div id="some-result"></div>
```

The spinner span sits *inside* the button so layout doesn't shift when it appears. The button gets `disabled` automatically (HTMX adds the attribute), and `htmx-indicator` opacity rules show the spinner.

---

## Key Design Decisions

- **Use HTMX's built-in `hx-indicator` + `htmx-indicator` class system.** No custom JS, no Alpine, no extra CSS. The behaviour ships with HTMX — we only need to put the right classes in the right places.
- **Spinner lives inside the button, not next to it.** Avoids layout shift when the spinner appears, and the button + spinner read as a single visual unit.
- **`hx-disabled-elt` over manual `disabled` toggling.** HTMX handles the disabled lifecycle automatically (added on send, removed on response). Don't try to do it ourselves.
- **Convert remaining non-HTMX flows to HTMX rather than mixing patterns.** The four target actions are all "click → wait → see result"; HTMX is the right primitive and we already have it. Keeps the codebase consistent and unblocks future polling for Celery.
- **`HX-Refresh: true` for sync.** Sync changes too many sections of the page to make partial updates worth it. A full refresh is the simplest correct behaviour and feels instantaneous because the data is already fetched.
- **Reuse the existing `redirect(...)` path for non-HTMX callers.** Detecting `HX-Request` and branching is a one-liner; preserving the redirect path keeps the views safe to hit from non-browser clients (curl, tests, future webhooks).
- **Error rendering via partial, not Django messages.** Django messages only show after a full page reload. For HTMX flows, render the error inline in the swap target so the user sees feedback without losing context.
- **No skeleton loaders.** Sync takes seconds, not minutes; a spinner is sufficient. Skeletons are worth the complexity only when content shape is predictable and load times exceed several seconds — neither holds here.

---

## Notes

- HTMX's spinner CSS only works when the indicator element is in the DOM at request time. If you put the spinner inside a `hx-swap="outerHTML"` target that itself gets replaced (like the entire `#use-cases-section`), the spinner will only be visible until the swap fires — which is exactly the right behaviour, but worth knowing during debugging.
- The `htmx-request` class is added to the element with `hx-indicator` (or to the requesting element if no indicator is set). The `htmx-indicator` class on the spinner reacts to that. If the spinner doesn't show, check the parent of `htmx-indicator` — it's usually a class-resolution issue.
- When testing locally, the LLM-backed actions will be slow enough to actually see the spinner; cheap actions (rating, demo load) may be too fast to observe. Use Chrome DevTools "Slow 3G" throttle or add a temporary `time.sleep(2)` in the view to validate the indicator visibly engages and disengages.
- Keep the spinner SVG small (16–20px). It should feel like part of the button text, not a UI element of its own.
- Open question: should we also indicate progress in the navbar (e.g. a thin top bar) for global awareness? Defer until we have a multi-tab use case. For now, local indicators only.