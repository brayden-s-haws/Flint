# Feature: Loading Indicators

**Source:** `devdocs/appdocs/post_mvp.md` — "Loading indicators for source sync and use case generation"
**Status:** Complete (Phases A–C done; D and E skipped — see notes below)
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

- **No async/Celery work in this feature.** Sync stays synchronous in the request cycle. Once Celery lands (post_mvp item #7) the sync spinner will evolve into a polling indicator that watches `SourceSyncLog.status`. Design the markup so that swap is mechanical: the button posts to the same URL, but the response becomes "started" + a poller. Don't pre-build the polling now. **Update (resolved):** the Celery migration shipped in `devdocs/featuredocs/celery-and-redis-setup.md`; sync now uses the polling pattern described there, which replaces the request-blocking spinner from this feature for the sync action specifically. Other actions (use case generation) still use this feature's spinner pattern.
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

- [x] On both `<form>` elements (Generate and Regenerate, lines 8 and 33), add:
  - `hx-disabled-elt="find button"` — disables the submit button while in flight
  - `hx-indicator="find .spinner"` — points at the spinner element inside the form
- [x] Inside each form, after the `<button>`, render `{% include 'components/_spinner.html' with label="Generating…" %}` wrapped in a span with class `spinner` so `find .spinner` resolves.
- [x] Verify visually: clicking Generate disables the button, swaps in the spinner, and on response the section is replaced (existing behaviour — the spinner disappears with the swap).
- [ ] ~~Verify error path: when `generate_intra_use_case_suggestions` returns a 400/500 (e.g. rate-limited or LLM failure), HTMX by default does NOT swap. The spinner stops, button re-enables, but the user sees no message.~~ **Deferred.** Two of the three error paths (missing source overview, rate-limited Regenerate) are already guarded by UI state and rarely trigger; the LLM-failure path is the only realistic one and produces a silent no-op rather than a broken state. To be picked up in a future bug bash (see "bug bash" section in `devdocs/appdocs/post_mvp.md`).
### Phase C — Source sync indicator (convert to HTMX) ✅

`templates/sources/source_detail.html:13-16` — plain form POST, full page reload.

- [x] Convert the Sync Now form to HTMX with `hx-post`, `hx-target="#sync-result"`, `hx-swap="innerHTML"`, `hx-disabled-elt="find button"`, `hx-indicator="find .spinner"`.
- [x] Add `{% include 'components/_spinner.html' with label="Syncing…" %}` inside the form after the button, and add a sibling `<div id="sync-result"></div>` outside the action row's flex container.
- [x] Update `sync_source` view to detect HTMX via `request.headers.get('HX-Request') == 'true'`. On both success and failure: return `HttpResponse('')` with `HX-Refresh: true` header so HTMX triggers a full reload — sync touches too many sections of the page to make partial updates worth it. Django messages survive the reload and surface success/error banners on the next GET.
- [x] Non-HTMX `redirect(...)` fallback preserved for direct (non-browser) callers.
- [x] **CSS gotcha resolved:** `.htmx-indicator` rules in `base.html` need `!important` to beat Tailwind CDN's `inline-flex` utility (Tailwind injects styles after our `<style>` block, so it wins on equal specificity). Use of `!important` is intentional and noted for cleanup when the Tailwind production build replaces the CDN (post_mvp item #6).
- [x] ~~**Known UX gap (deferred):** sync request blocks the request cycle for 20–60s on first sync because LLM source-overview generation runs synchronously.~~ **Resolved:** the Celery migration (`devdocs/featuredocs/celery-and-redis-setup.md`) moved sync into a background task with a 2-second polling indicator; the request itself now returns in <100ms. Intermediate "Generating insights…" status would still be a nice-to-have but is no longer a UX blocker since the page is responsive throughout.

### Phase D — Test Connection indicator (skipped)

**Decision:** No spinner needed. Test Connection completes in well under a second — the connector opens a network handle and returns a boolean. By the time the user could perceive a spinner, the page has already reloaded with the result via Django messages. Adding a spinner here would be visual noise, not feedback.

The form stays as a plain POST → redirect → flash message. No work to do.

### Phase E — Load Demo Data indicator (skipped)

**Decision:** No spinner needed. The view only creates three `Source` records (three DB writes) — it does not run sync on them. Sub-second response. Same rationale as Phase D: spinner would be noise.

The form stays as a plain POST → redirect → flash message. No work to do.

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