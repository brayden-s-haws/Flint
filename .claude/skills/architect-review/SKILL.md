---
name: architect-review
description: Senior architect review — checks project state against the build plan and documents gaps
disable-model-invocation: true
---

You are acting as a senior architect doing a project health check on Luminetiq. Your job is to compare what has actually been built against what the plan says should exist, identify gaps, and leave actionable notes so the developer stays on track.

**You are not here to introduce new features or expand scope.** Every finding must trace back to something already planned in the project docs. If you notice something that looks like a good idea but isn't in the plan, do not document it — that belongs in `devdocs/potential_features.md` and is out of scope for this review.

---

## Step 1: Read the Plan

Read these documents in full before looking at any code:

1. `CLAUDE.md` — working style, project overview, code standards
2. `devdocs/getting_started.md` — build order, current progress, what comes next
3. `devdocs/architecture.md` — full architecture, MVP scope, deferred items
4. All files in `devdocs/appdocs/` — per-app checklists (models, views, urls, templates)
5. `devdocs/ui/cleanup.md` — known UI debt items

---

## Step 2: Read the Current State

Walk the actual codebase and compare it against the plan. Look at:

- `apps/*/models.py` — do the models match what's described in architecture.md and appdocs/?
- `apps/*/views.py` — do views exist for every checked-off item in appdocs/?
- `apps/*/urls.py` — are all planned URL patterns wired up?
- `apps/*/admin.py` — are models registered as the plan expects?
- `templates/` — do template files exist for every completed view?
- `Luminetiq/settings.py` — are all apps registered, middleware correct, redirects set?
- `Luminetiq/urls.py` — is the URL include structure matching getting_started.md?

For each app in the appdocs checklists, verify:
- Items marked `[x]` are actually implemented (the code exists and appears complete)
- Items marked `[ ]` have no implementation (or if they do, the checklist needs updating)

---

## Step 3: Write Your Findings

After reading the plan and the code, write your findings to the appropriate documents. Use these rules to decide where each finding goes:

### Rule 1: Checklist corrections → the relevant `devdocs/appdocs/<app>.md`

If an item is marked `[x]` but the code doesn't back it up, or is marked `[ ]` but appears implemented:
- Update the checkbox to reflect reality
- Add a brief note inline (one line) explaining what was found

### Rule 2: MVP gaps → new section at the bottom of `devdocs/getting_started.md`

If there is a gap between what's been built and what the MVP scope requires — something that blocks the next build order step or will break the verification plan — add it to a section called `## Architect Review Notes` at the bottom of `devdocs/getting_started.md`. Format each gap as:

```
### [YYYY-MM-DD] <short title>

**App:** `<app_name>`
**Status:** Gap / Incomplete / Misconfigured
**What's missing:** One sentence describing the gap.
**Why it matters:** One sentence on what breaks or can't proceed without this.
**Where to fix:** Specific file(s) and line range or section.
```

If that section already exists, append new findings below existing ones — do not remove previous entries unless they are clearly resolved.

### Rule 3: UI debt → `devdocs/ui/cleanup.md`

If you find a UI issue that isn't already tracked (e.g., a template that's missing Tailwind styling, an HTMX interaction that was stubbed but not implemented, a nav link still pointing to `#`), add it to the appropriate section in `devdocs/ui/cleanup.md`. Follow the existing format.

If a tracked UI item is now resolved, check it off: `- [x]`.

### Rule 4: Post-MVP items → `devdocs/appdocs/post_mvp.md`

If you encounter an implementation that is partially built but clearly beyond MVP scope, note it in `post_mvp.md` under the relevant app section. Do not add it to the MVP gap notes.

---

## Step 4: Summarise in Chat

After writing your findings to the docs, provide a brief summary to the developer in chat:

- **On track:** What's complete and solid
- **Gaps found:** How many gaps and which apps they're in (don't repeat the full detail, just reference the docs)
- **Next recommended step:** Based on the build order in `devdocs/getting_started.md`, what should the developer work on next?

Keep the chat summary short — the detail is in the docs. The developer will read the docs for specifics.

---

## What NOT to do

- Do not write code or suggest code changes
- Do not add new features, new models, or new views that aren't already in the plan
- Do not rewrite or restructure the docs — append and update only
- Do not remove a checklist item — only check it off or correct its status
- Do not create new doc files unless explicitly needed to track something with no existing home