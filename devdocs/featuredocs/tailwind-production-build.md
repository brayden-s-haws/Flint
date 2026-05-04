# Feature: Tailwind CDN → Production Build

**Source:** `devdocs/appdocs/post_mvp.md` — "infrastructure — Tailwind CDN to Production Build"
**Status:** Complete
**Target phase:** Post-MVP Phase 2 (item #6)
**Branch:** `feature/tailwind-prod`

---

## Overview

Replace the Tailwind play CDN script (`<script src="https://cdn.tailwindcss.com">`) with a proper npm-based Tailwind build that compiles a static `output.css` containing only the utility classes actually used in the codebase. The CDN approach is fine for development but ships ~3MB of unused CSS, defers all class scanning to the browser, and breaks offline use. A production build produces a small, purged stylesheet that's served like any other static asset and that allows custom CSS rules to coexist with utility classes without `!important` (a workaround currently required by the loading-indicators feature).

---

## Dependencies

- [x] Node.js + npm available on the dev machine (verify before starting; install via `nvm` or `homebrew` if missing)
- [x] `static/` directory exists and is wired through `STATICFILES_DIRS` in `Flint/settings.py` (already configured at line 130–131)
- [x] All existing templates use Tailwind utility classes the build can scan (no runtime class generation)

---

## Implementation Checklist

This is a small, self-contained migration. No phases — single flat checklist.

### Initialise npm in the project

- [x] Run `npm init -y` from project root to create `package.json`
- [x] Add `node_modules/` and `package-lock.json` decision to `.gitignore` (commit `package-lock.json` for reproducible installs; ignore `node_modules/`)

### Install Tailwind

- [x] `npm install -D tailwindcss@^3` (pin to v3 — v4 has different config syntax and is not what `post_mvp.md` describes)
- [x] Generate config via `npx tailwindcss init` — produces `tailwind.config.js` at project root

### Configure `tailwind.config.js`

- [x] Set `content` to scan all template directories: `./templates/**/*.html` and `./apps/**/templates/**/*.html`.
- [x] Moved the `theme.extend` block (flint colors + Geist/Inter font family) from `base.html` into `tailwind.config.js` verbatim.
- [x] `corePlugins` defaults left as-is — no utilities to disable.

### Set up the CSS source file

- [x] Created `static/css/input.css` with the three `@tailwind` directives and the custom CSS rules (markdown-content and htmx-indicator) appended after.
- [x] Both `!important` flags dropped from the `.htmx-indicator` rules. Verified post-build that spinner still hides/shows correctly with natural specificity.

### Add build scripts to `package.json`

- [x] `build:css` script (one-shot, minified) and `watch:css` script (dev watcher) both added.
- [x] Documented in `CLAUDE.md` "Common Commands" instead of `getting_started.md` — `CLAUDE.md` is the more visible entry point for both human and AI sessions.

### Wire the compiled CSS into base.html

- [x] Removed the Tailwind CDN script, the inline `tailwind.config = {...}` block, and the inline `<style>` block (which also cleared the orphaned/broken CSS lines that had accumulated).
- [x] Replaced with a single `<link rel="stylesheet" href="{% static 'css/output.css' %}">` placed before the HTMX script.
- [x] `{% load static %}` directive preserved.
- [x] `base.html` now ~29 lines (down from ~75).

### Build and verify

- [x] `npm run build:css` produces `static/css/output.css` (~30KB minified).
- [x] Visually confirmed: source detail page (flint colors, hover states, demo banner), source/insight lists, forms, markdown rendering, HTMX spinner all render correctly.
- [ ] ~~Run `python manage.py collectstatic --noinput`~~ — **deferred until first real deploy.** Django's static-file pipeline already finds `output.css` via `STATICFILES_DIRS` during dev. The collectstatic check is relevant only when a production deployment is set up, which doesn't exist yet.

### Update `.gitignore`

- [x] `node_modules/` added under a "Node / npm" section.
- [x] `static/css/output.css` committed to git per the design decision (solo dev, no CI build step).

### Documentation

- [x] Added `npm run build:css` and `npm run watch:css` to "Common Commands" in `CLAUDE.md`.
- [x] Added a Tailwind bullet to "Configuration Notes" in `CLAUDE.md` naming the three files (`tailwind.config.js`, `static/css/input.css`, `static/css/output.css`) and explicitly warning future-Claude not to put rules back into `base.html`.

---

## Key Design Decisions

- **Tailwind v3, not v4.** v4 ships with a different config syntax (CSS-first, `@theme` directive) and a different toolchain. `post_mvp.md` describes the v3 npm flow; staying on v3 minimises surprises. Worth revisiting v4 once the migration is stable.
- **Standalone CLI, not PostCSS.** Tailwind ships a self-contained CLI binary that handles input → output without needing a separate PostCSS pipeline. Simpler for a solo project.
- **Commit `output.css` to git.** For a solo dev with no CI build step, committing the compiled file is the lowest-friction path. The trade-off is one more file to update on PRs that change classes; the alternative (CI build) adds infra complexity that's not worth it yet.
- **Keep custom CSS rules in `input.css`, not as inline `<style>` in templates.** Centralises all custom CSS and lets Tailwind's `@layer` directives (if needed later) work correctly. The current `<style>` block in `base.html` is the only inline CSS in the project and moves cleanly.
- **Drop `!important` from `.htmx-indicator`.** With a single compiled stylesheet, rule order is predictable. The Tailwind utility for `.inline-flex` and our custom `.htmx-indicator` rules will both be in `output.css` in a deterministic order, so we can rely on natural specificity. Validate after build before removing the `!important`.

---

## Notes

- **`base.html` will get noticeably shorter.** Roughly 25 lines of inline JS/CSS get removed and replaced by one `<link>` tag.
- **The `flint` color palette is the only `theme.extend` content.** When moving to `tailwind.config.js`, the structure is `module.exports = { content: [...], theme: { extend: { colors: { flint: {...} }, fontFamily: {...} } } }`.
- **Open question: do we need a watcher for production?** No — `npm run build:css --minify` runs once at deploy time. The watcher is dev-only.
- **Tailwind class name strings only — no runtime class generation.** Verify by grepping for any `f"..."` Python strings or template `{% if %}` blocks that build class names dynamically; the `content` scanner only sees literal class names.
- **Heroicons / extra icon libraries:** none in use today (the existing spinner uses an inline SVG with currentColor). No icon-library install needed.
- **CDN script tag URL:** the integrity hash on the HTMX `<script>` tag (line 37 of `base.html`) is unrelated and stays as-is. Only the Tailwind script and inline config block get removed.
- **`collectstatic` and deployment:** when you eventually deploy, ensure the deploy process either (a) runs `npm run build:css` before `collectstatic` or (b) commits `output.css` so it's already in `static/`. Option (b) is the current decision.