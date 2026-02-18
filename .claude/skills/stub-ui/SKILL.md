---
name: stub-ui
description: Stub out an HTML template with TODO comments guiding the developer on what to build
disable-model-invocation: true
argument-hint: "[file path]"
---

Stub out the HTML template at `$ARGUMENTS` with detailed TODO comments that guide the developer through building the page. **Do not write the actual implementation code.** Instead, add `<!-- TODO(stub): ... -->` comments that describe what needs to be built at each point in the file.

## Before Stubbing

1. Read the template file provided in the argument
2. Read relevant docs to understand what the page should contain:
   - `devdocs/architecture.md` — overall app structure and features
   - `devdocs/getting_started.md` — build order and patterns
   - `devdocs/ui/cleanup.md` — known UI items
   - App-specific docs in `devdocs/appdocs/` if they exist
3. Read the related view to understand what context variables and form are available to the template
4. Read `templates/base.html` to understand what blocks are available to extend

## Stubbing Rules

- **Do not write HTML, CSS, or JS code** in the file — only TODO comments and the minimal skeleton (extends, block tags)
- Use `<!-- TODO(stub): ... -->` for all guidance comments
- Each TODO should describe **what** to build and **why**, with enough detail that the developer can look up the right approach
- Reference specific Django template tags, Tailwind classes, or HTMX attributes by name when relevant, but don't write the full implementation
- Mention context variables and form fields available from the view
- Call out accessibility considerations where relevant
- Order TODOs top-to-bottom matching the visual layout of the page
- If the page extends base.html, start with `{% extends 'base.html' %}` and use the appropriate blocks

## After Stubbing

- Provide a brief summary in the chat listing what was stubbed and any decisions the developer should think about
- Mention relevant Django docs or patterns they should reference
- Use pseudocode or generic examples in the chat to explain concepts — do not give the exact answer

## Managing Stubs

- Only manage `<!-- TODO(stub): ... -->` comments — never touch `<!-- TODO: ... -->` or `<!-- TODO(review): ... -->` comments
- On subsequent runs, remove TODO(stub) comments for sections the developer has implemented
- Add new TODO(stub) comments if the requirements have changed or new context is available
