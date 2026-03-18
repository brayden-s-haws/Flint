---
name: plan-feature
description: Generate a featuredoc — a structured implementation checklist for a post-MVP feature
disable-model-invocation: true
argument-hint: "[feature name or slug]"
---

Generate a featuredoc for the feature named in `$ARGUMENTS`. A featuredoc is a structured implementation checklist that lives in `devdocs/featuredocs/` and serves as the canonical reference for everything that needs to be built to ship this feature.

The featuredoc is used by `/code-review` and `/branch-review` as the completeness reference when reviewing work on a feature branch. It must be specific enough that those skills can determine, from code alone, whether a checklist item is done or not.

---

## Step 1: Find the Feature

Look for the named feature in these documents:

1. `devdocs/appdocs/post_mvp.md` — detailed feature sections (check section headings)
2. `devdocs/potential_features.md` — shorter feature bullets (check all categories)

If the feature is found in both, use the `post_mvp.md` section as the primary source (it has more detail) and note the `potential_features.md` entry.

If the argument is ambiguous (e.g., "queries" could match the queries app section and several potential features), pick the most specific match and note in chat which one you used.

---

## Step 2: Read Context Docs

Before writing the featuredoc, read:

1. `devdocs/architecture.md` — understand the overall app structure and which apps already exist
2. `devdocs/getting_started.md` — understand build order and what will exist by the time this feature is built
3. `devdocs/appdocs/<app>.md` for any existing app the feature touches — understand what's already built vs. what needs to be added

If the feature requires a **new app** (e.g., `apps/queries/`, `apps/ontology/`), note this clearly in the featuredoc.

---

## Step 3: Write the Featuredoc

Write the file to `devdocs/featuredocs/<slug>.md` where `<slug>` is a short, lowercase, hyphenated name derived from the feature (e.g., `natural-language-to-sql.md`, `ontology.md`, `amundsen-integration.md`).

Use this structure:

---

```markdown
# Feature: <Full Feature Name>

**Source:** `devdocs/appdocs/post_mvp.md` — <section name> (or `devdocs/potential_features.md`)
**Status:** Not started
**Target phase:** Post-MVP Phase <N> (or "any time after MVP" if not sequenced)

---

## Overview

2–4 sentences: what this feature does, why it's valuable, and how it fits into the broader product.

---

## Dependencies

What must exist and be working before this feature can be built. Be specific — name the models, apps, and infrastructure required.

- [ ] `apps/<app>/` — what specifically must be in place
- [ ] `apps/<app>/` — another dependency
- [ ] Infrastructure (e.g., Celery + Redis, pgvector, etc.) if required

---

## New App: `apps/<app>/` *(omit this section if no new app is needed)*

If this feature lives in a new app, describe it here. Otherwise skip this section.

Brief description of what this app is responsible for.

---

## Implementation Checklist

Organize by phase if the source docs describe a phased build. If not phased, use a single flat checklist. Each item must be specific enough to verify from code — not "add views" but "add `QueryHistoryListView` at `/queries/`".

### Phase 1 — <Name>

#### Models
- [ ] `ModelName` — brief description of what it stores and its key fields
- [ ] `ModelName` — ...

#### Views & URLs
- [ ] `ViewName` — `GET /path/` — what it does
- [ ] `ViewName` — `POST /path/` — what it does

#### Templates
- [ ] `app/template_name.html` — what it renders

#### Settings & Wiring
- [ ] Register `apps/<app>` in `INSTALLED_APPS`
- [ ] Include `apps/<app>/urls.py` in `Flint/urls.py` with `app_name = '<app>'`
- [ ] Any middleware, signals, or app config wiring needed

#### Tests *(note any critical test cases worth calling out)*
- [ ] Test <specific behavior>

---

### Phase 2 — <Name> *(add more phases as needed)*

*(same structure as Phase 1)*

---

## Key Design Decisions

Note any architectural choices that were made in the source docs that the developer should be aware of. This is not a list of things to do — it's context for why things are structured the way they are.

- **<decision>:** explanation
- **<decision>:** explanation

---

## Notes

Anything else the developer should know: gotchas, external docs to read, libraries to install, security considerations specific to this feature.
```

---

## Step 4: Summarise in Chat

After writing the featuredoc, tell the developer:

- **File written:** `devdocs/featuredocs/<slug>.md`
- **Phases:** how many phases and a one-line description of each
- **Key dependencies:** the most important things that must exist first
- **New app required:** yes/no, and the app name if yes
- **Suggested branch name:** e.g., `feature/queries-phase-1` or `feature/ontology`

Keep the summary short — the detail is in the file.

---

## What NOT to do

- Do not write implementation code — only the checklist doc
- Do not add items to the checklist that aren't in the source docs — scope is defined by what's already planned
- Do not create a featuredoc for MVP features — those are tracked in `devdocs/appdocs/` and this would duplicate them
- Do not modify `post_mvp.md` or `potential_features.md` — the featuredoc is a separate artefact, not a replacement
- Do not guess at details that aren't in the source docs — if something is unclear, note it in the Notes section as an open question