---
name: branch-review
description: Context-aware branch review — reviews all changed files on the current branch, scoped to the current feature. Defaults to MVP boundary; pass "post-mvp" to review without that restriction.
disable-model-invocation: true
---

## Mode

Check the argument passed to this skill invocation:

- **No argument or `mvp`** — default mode. Stay within the MVP boundary. Do not flag post-MVP gaps. This is the standard mode during active MVP development.
- **`post-mvp`** — relaxed mode. The MVP boundary restriction is lifted. You may flag architectural gaps, missing features, and improvements that go beyond MVP scope. Rule 1 in Step 3 does not apply.

All other behaviour (scope rules 2–4, inline comment format, checklist updates) applies in both modes.

---

Review everything changed on the current branch. Your job is to catch real issues in the work that was done — not to suggest work from other features. Stay scoped.

Add inline `TODO(review)` comments directly in each file that has findings, using the correct comment syntax for the file type. Remove `TODO(review)` comments that are already resolved. Summarise all findings in chat when done.

---

## Comment Syntax by File Type

Use the correct comment syntax based on the file extension:

- **Python** (`.py`): `# TODO(review): message`
- **HTML/Templates** (`.html`): `<!-- TODO(review): message -->`
- **JavaScript** (`.js`): `// TODO(review): message`
- **CSS** (`.css`): `/* TODO(review): message */`

Only manage `TODO(review)` comments — never touch `TODO(stub)` or plain `TODO` comments.

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
- Are any checklist items marked `[ ]` in the appdoc/featuredoc that this file was supposed to address?

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

**Rule 1 — MVP boundary** *(mvp mode only)*: If a finding is about something that belongs post-MVP (not in any `devdocs/appdocs/` checklist, or explicitly noted as post-MVP in `devdocs/architecture.md`), do not include it. Post-MVP gaps are not this branch's problem. Skip this rule entirely in `post-mvp` mode.

**Rule 2 — Feature boundary**: If a finding is about something that belongs to a different app or a different feature branch, do not include it. Only report gaps in the apps this branch is touching.

**Rule 3 — Not-yet-built is not a bug**: If the appdoc shows an item as `[ ]` but it's clearly planned for a future branch (e.g., the sources app views when this branch is about core), do not report it. Only flag `[ ]` items that this branch was supposed to address based on the branch name and changed file list.

**Rule 4 — Stubs are expected**: If a file has `TODO(stub)` comments marking unimplemented sections that are intentionally left for later, do not flag those as gaps. Only flag stub sections that the developer has clearly started but left broken or incomplete.

---

## Step 4: Write Inline TODO(review) Comments

For each file that has findings:

- **Remove resolved `TODO(review)` comments**: If the file already has `TODO(review)` comments from a previous review and the code now satisfies them, delete those comments.
- **Add new `TODO(review)` comments**: Add comments inline at the specific lines that need attention, using the correct syntax for the file type.
- **Clean up `TODO(stub)` comments**: If a `TODO(stub)` section has been implemented, remove it. Leave stub TODOs in place where the section is still empty or incomplete.
- **Leave plain `TODO` comments alone**: Never modify or remove `TODO` comments written by the developer.

If a file has no findings, do not touch it.

---

## Step 5: Apply Checklist Corrections

After adding inline comments, update the relevant checklists to match reality. If a featuredoc exists for this branch's feature, update it. Otherwise update the relevant appdoc.

- Mark `[x]` on items that are now implemented
- Mark `[ ]` on items that were checked off but the code doesn't back up
- Do not add new items — the checklists are the source of truth for scope

---

## Step 6: Summarise in Chat

After adding inline comments and updating checklists, give the developer a short summary:

- **Branch:** what it accomplishes
- **Files reviewed:** how many
- **Issues found:** count and which files (the inline TODOs have the detail)
- **Commit readiness:** yes, no, or with caveats
- **Next step:** based on `devdocs/getting_started.md`, what should they work on after this branch

Keep the chat summary short — the inline `TODO(review)` comments have the detail.

---

## What NOT to do

- Do not write a report file — all findings go inline as `TODO(review)` comments
- Do not flag post-MVP gaps in `mvp` mode — those belong in `devdocs/appdocs/post_mvp.md` and are not this branch's concern
- Do not flag gaps in apps not touched by this branch
- Do not suggest new features or architectural improvements not already in the plan
- Do not rewrite or restructure source files
- Do not remove appdoc checklist items — only update their `[ ]` / `[x]` status
- Do not modify or remove plain `TODO` or `TODO(stub)` comments
