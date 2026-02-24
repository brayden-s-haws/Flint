---
name: branch-review
description: Context-aware branch review — reviews all changed files on the current branch, scoped to the current feature and MVP boundary
disable-model-invocation: true
---

Review everything changed on the current branch. Your job is to catch real issues in the work that was done — not to suggest work from other features, not to suggest post-MVP improvements. Stay scoped.

**Do not write inline TODO comments in files.** Instead, write all findings to a report at `devdocs/reviews/branch-review.md`. This keeps the source files clean and gives the developer one place to work through before committing.

---

## Step 1: Establish Scope

Run these two commands to understand what you're reviewing:

1. `git diff main...HEAD --name-only` — the list of files changed on this branch
2. `git rev-parse --abbrev-ref HEAD` — the current branch name

From the branch name and the changed file list, determine:
- **Which apps are in scope** — e.g., if `apps/core/` files changed, the `core` app is in scope
- **What this branch is trying to accomplish** — infer from the branch name (e.g., `feature/core-mixin-and-dashboard` → building core mixins and the dashboard view/template)

You will use this scope to filter every finding in Step 3.

---

## Step 2: Read the Plan

Read these documents before reviewing any code:

1. `devdocs/architecture.md` — MVP boundary, what is and isn't in scope for v1
2. `devdocs/getting_started.md` — build order and current progress (helps you understand what the developer should have built on this branch vs what comes later)
3. **Check for a featuredoc first:** Look in `devdocs/featuredocs/` for a file matching this branch's feature (e.g., branch `feature/queries-phase-1` → check for `devdocs/featuredocs/natural-language-to-sql.md` or similar). If one exists, **use it as the primary completeness reference** — it defines exactly what needs to be done for this feature.
4. **Fall back to appdocs if no featuredoc:** If no featuredoc exists for this branch's feature, read `devdocs/appdocs/<app>.md` for each in-scope app.

Do **not** read appdocs or featuredocs for apps/features not touched by this branch. Their requirements are out of scope.

---

## Step 3: Review Each Changed File

For each file in the changed file list, read it and apply the checklist below. Keep findings tightly scoped using the rules that follow.

### Review Checklist

#### Completeness
- Does this file satisfy the checklist items for its app that are expected on this branch?
- Are any checklist items marked `[ ]` in the appdoc that this file was supposed to address?

#### Type Hints (Python files only)
- All function parameters and return types annotated
- `from __future__ import annotations` present at the top
- `typing` imports used where needed

#### Python Best Practices (Python files only)
- PEP 8 naming
- Clean import grouping: stdlib → blank line → third-party → blank line → local
- No unnecessary complexity

#### Django Best Practices
- Models: field types, constraints, `Meta`, `__str__`
- Views: correct CBV vs FBV choice, correct mixins, `login_url` set when using `LoginRequiredMixin`
- URLs: namespaced, RESTful
- Templates: correct block names, `{% url %}` namespaces match `urls.py` `app_name`

#### Security
- No hardcoded secrets or credentials
- Proper use of Django's built-in protections
- Input validation at system boundaries

### Scope Rules — apply these before writing any finding

**Rule 1 — MVP boundary**: If a finding is about something that belongs post-MVP (not in any `devdocs/appdocs/` checklist, or explicitly noted as post-MVP in `devdocs/architecture.md`), do not include it. Post-MVP gaps are not this branch's problem.

**Rule 2 — Feature boundary**: If a finding is about something that belongs to a different app or a different feature branch, do not include it. Only report gaps in the apps this branch is touching.

**Rule 3 — Not-yet-built is not a bug**: If the appdoc shows an item as `[ ]` but it's clearly planned for a future branch (e.g., the sources app views when this branch is about core), do not report it. Only flag `[ ]` items that this branch was supposed to address based on the branch name and changed file list.

**Rule 4 — Stubs are expected**: If a file has `TODO(stub)` comments marking unimplemented sections that are intentionally left for later, do not flag those as gaps. Only flag stub sections that the developer has clearly started but left broken or incomplete.

---

## Step 4: Write the Report

Write your findings to `devdocs/reviews/branch-review.md`. Create the file if it doesn't exist. If it does exist, replace the entire contents — this report always reflects the current state of the branch, not a history of reviews.

### Report format

```markdown
# Branch Review: <branch-name>

**Date:** YYYY-MM-DD
**Files reviewed:** N
**Apps in scope:** app1, app2

---

## Summary

One paragraph: what this branch accomplishes, what's solid, and whether it's ready to commit.

---

## Findings

### <filename> — <pass | needs attention>

<One sentence describing the overall state of this file.>

- **[Category]** Finding description. ← only include if there's an actual issue
- **[Category]** Finding description.

*(If the file is clean, write "No issues found." and move on.)*

---

## Checklist Corrections

If any checklist items need to be updated to reflect what was built on this branch, list them here. Reference whichever doc is authoritative for this branch — the featuredoc if one exists, otherwise the appdoc:

- `devdocs/featuredocs/<feature>.md` — `<item>` should be marked `[x]` (now implemented)
- `devdocs/featuredocs/<feature>.md` — `<item>` should be marked `[ ]` (marked done but code not found)
- `devdocs/appdocs/<app>.md` — `<item>` should be marked `[x]` (now implemented)

Apply these corrections to the relevant files after writing the report.

---

## Commit Readiness

**Ready to commit:** Yes / No / With caveats

If no or with caveats, list the blockers:
- <specific issue that must be resolved before committing>
```

---

## Step 5: Apply Checklist Corrections

After writing the report, update the relevant checklists to match reality. If a featuredoc exists for this branch's feature, update it. Otherwise update the relevant appdoc.

- Mark `[x]` on items that are now implemented
- Mark `[ ]` on items that were checked off but the code doesn't back up
- Do not add new items — the checklists are the source of truth for scope

---

## Step 6: Summarise in Chat

After writing the report and updating checklists, give the developer a short summary:

- **Branch:** what it accomplishes
- **Files reviewed:** how many
- **Issues found:** count by severity (blocker vs minor)
- **Commit readiness:** yes, no, or with caveats
- **Next step:** based on `devdocs/getting_started.md`, what should they work on after this branch

Keep the chat summary to under 10 lines. The report has the detail.

---

## What NOT to do

- Do not write inline `TODO(review)` comments in source files — all findings go in the report
- Do not flag post-MVP gaps — those belong in `devdocs/appdocs/post_mvp.md` and are not this branch's concern
- Do not flag gaps in apps not touched by this branch
- Do not suggest new features or architectural improvements not already in the plan
- Do not rewrite or restructure source files — this is read-only except for appdoc checkbox updates
- Do not remove appdoc checklist items — only update their `[ ]` / `[x]` status
