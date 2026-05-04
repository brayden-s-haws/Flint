# Feature: Tailwind CDN → Production Build

**Source:** `devdocs/appdocs/post_mvp.md` — "infrastructure — Tailwind CDN to Production Build"
**Status:** Not started
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

- [ ] Set `content` to scan all template directories that use Tailwind classes:
  - `templates/**/*.html`
  - `apps/**/templates/**/*.html` (if any app-local templates exist; check)
- [ ] Move the `theme.extend` block from `templates/base.html` (lines 12–35 — `flint` color palette and `Geist`/`Inter` font family) into `tailwind.config.js`. Verbatim copy — same colors, same names.
- [ ] Confirm `corePlugins` defaults are appropriate (no need to change unless we want to disable specific utilities)

### Set up the CSS source file

- [ ] Create `static/css/input.css` containing the three Tailwind directives:
  ```
  @tailwind base;
  @tailwind components;
  @tailwind utilities;
  ```
- [ ] Move the existing custom rules from `templates/base.html` `<style>` block (lines 38–57 — `.markdown-content` rules and `.htmx-indicator` rules) into `static/css/input.css`, placed after the `@tailwind` directives so they get compiled into the final stylesheet
- [ ] Drop the `!important` from the `.htmx-indicator` rules — they are no longer needed once Tailwind compiles into a single stylesheet with predictable rule order. Verify after build that the spinner still hides/shows correctly.

### Add build scripts to `package.json`

- [ ] Add a `build:css` script: `tailwindcss -i ./static/css/input.css -o ./static/css/output.css --minify`
- [ ] Add a `watch:css` script for development: `tailwindcss -i ./static/css/input.css -o ./static/css/output.css --watch`
- [ ] Document both in `devdocs/getting_started.md` (or wherever the run instructions live) so the next-time-running developer knows to run `npm run watch:css` alongside `python manage.py runserver`

### Wire the compiled CSS into base.html

- [ ] Replace the Tailwind CDN `<script src="https://cdn.tailwindcss.com">` and the inline `tailwind.config = {...}` `<script>` block (lines 10–36) with a single `<link rel="stylesheet" href="{% static 'css/output.css' %}">` tag
- [ ] Remove the now-empty `<style>` block (lines 38–57) — its contents have moved to `input.css`
- [ ] Keep the `{% load static %}` directive at the top of `base.html` (already present at line 1)

### Build and verify

- [ ] Run `npm run build:css` once and confirm `static/css/output.css` is generated
- [ ] Reload every page in the app and visually confirm styling is intact — particularly check:
  - Source detail page (uses many `flint-*` colors, `card`, hover states)
  - Source list, insight list (table rendering)
  - Forms (the styled widget classes from CLAUDE.md)
  - The HTMX spinner in the use case section and source sync (must still hide/show correctly without the `!important`)
  - Markdown rendering (`.markdown-content` rules)
  - Demo banner (yellow palette)
- [ ] Run `python manage.py collectstatic --noinput` to confirm Django can collect the new CSS file (relevant for production deployment)

### Update `.gitignore`

- [ ] Add `node_modules/` to `.gitignore`
- [ ] Decide on `static/css/output.css` — generally **commit it** for solo-dev simplicity (Django's `collectstatic` will pick it up and Heroku/Render-style deploys won't need to install npm). If we move to a CI-driven deploy that runs the build, we can remove it from git later.

### Documentation

- [ ] Update `CLAUDE.md` "Common Commands" section to add the `npm run watch:css` instruction alongside `runserver`
- [ ] Note in `CLAUDE.md` that Tailwind config now lives in `tailwind.config.js` (so future template edits don't try to put colors in `base.html`)

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