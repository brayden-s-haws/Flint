---
name: code-review
description: Review a completed file for code quality, completeness, and best practices
disable-model-invocation: true
argument-hint: "[file path]"
---

Review the file at `$ARGUMENTS` as a code review. **Do not write code changes to the file.** Instead, add inline TODO(review) comments directly in the file at the relevant lines so the developer can work through them. Always use the `(review)` tag to distinguish these from the developer's own TODO comments. Only manage TODO(review) comments — never touch TODO comments written by the developer.

## Comment Syntax by File Type

Use the correct comment syntax based on the file extension:

- **Python** (`.py`): `# TODO(review): message`
- **HTML/Templates** (`.html`): `<!-- TODO(review): message -->`
- **JavaScript** (`.js`): `// TODO(review): message`
- **CSS** (`.css`): `/* TODO(review): message */`

The same rules apply regardless of syntax: only manage TODO(review) comments, never touch the developer's own TODO comments.

## Review Checklist

### 1. Completeness (MVP Scope)
- Does the code satisfy all requirements defined in `devdocs/architecture.md` and `devdocs/getting_started.md` for this app/model?
- Are all required fields, methods, and relationships present?
- Is anything missing that the MVP scope expects?

### 2. Type Hints
- Do all function parameters have type annotations?
- Do all functions have return type annotations?
- Is `from __future__ import annotations` present at the top of the module?
- Are `typing` imports used where needed (`Optional`, `list`, `dict`, etc.)?

### 3. Python Best Practices
- Follows PEP 8 naming conventions
- Appropriate use of docstrings
- No unnecessary complexity
- Clean imports (grouped: stdlib, third-party, local)

### 4. Django Best Practices
- Models: appropriate field types, constraints, `Meta` options, `__str__` methods
- Views: correct use of class-based vs function-based views, proper mixins
- URLs: namespaced, RESTful naming
- Admin: models registered with useful `list_display`, `search_fields` where appropriate
- Migrations: no obvious issues

### 5. Security
- No hardcoded secrets or credentials
- Proper use of Django's built-in protections
- Input validation where needed

## Output Format

- Read the file provided in the argument
- Read relevant architecture/getting_started docs to understand what the file should contain
- **Remove resolved TODOs**: If the file has existing TODO(review) comments from a previous review and the code now satisfies them, delete those TODO comments
- **Add new TODOs**: Add TODO(review) comments inline at specific lines that still need attention, using the correct comment syntax for the file type (see Comment Syntax section above)
- **Leave developer TODOs alone**: Never modify or remove TODO comments (without the `(review)` tag) — those belong to the developer
- After updating TODOs, provide a brief summary of findings grouped by category
- If the file looks good and all TODOs are resolved, say so — don't invent issues that aren't there