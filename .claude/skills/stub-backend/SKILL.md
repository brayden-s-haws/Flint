---
name: stub-backend
description: Stub out a backend Python file with TODO comments guiding the developer on what to build
disable-model-invocation: true
argument-hint: "[file path]"
---

Stub out the Python file at `$ARGUMENTS` with detailed TODO comments that guide the developer through implementing it. **Do not write the actual implementation code.** Instead, add `# TODO(stub): ...` comments that describe what needs to be built at each point in the file.

## Before Stubbing

1. Read the file provided in the argument
2. Identify the file type from its name: `signals.py`, `middleware.py`, `views.py`, `forms.py`, or `apps.py`
3. Identify which app it belongs to from its path (e.g., `apps/accounts/signals.py` → accounts app)
4. Read relevant docs:
   - `devdocs/architecture.md` — overall patterns and multi-tenancy approach
   - `devdocs/appdocs/<app>.md` — the checklist for this specific app
   - `apps/<app>/models.py` — understand the data structures the file will work with
   - For views: also read `apps/<app>/urls.py` to understand what routes exist

## Stubbing Rules

- **Do not write Python implementation code** — only TODO comments and the minimal skeleton (see File Type Skeletons below)
- Use `# TODO(stub): ...` for all guidance comments
- Each TODO should describe **what** to build and **why**, with enough detail to look up the right approach
- Reference specific Django patterns, signals, mixins, or decorators by name — but don't implement them
- Always include `from __future__ import annotations` at the top — this is a project requirement
- Always note where type hints are needed on functions and what the expected types are
- Order TODOs top-to-bottom matching the logical execution flow of the file

## File Type Skeletons

Each file type has a standard skeleton. Write only the skeleton structure plus TODO comments — no logic.

### signals.py

Skeleton: `from __future__ import annotations` header, import placeholders, one handler function stub per signal needed.

Key TODOs to include:
- What signal to connect to (`post_save`, etc.) and on which sender model
- The required function signature (`sender`, `instance`, `created`, `**kwargs`) and type hints
- What objects to create inside the handler and in what order (e.g., create Account before AccountMembership)
- That `created` must be checked before doing anything — explain why (signal fires on updates too)
- The `@receiver` decorator and where to import it from

### middleware.py

Skeleton: `from __future__ import annotations` header, import placeholders, one class with `__init__` and `__call__` stubs.

Key TODOs to include:
- The `__init__(self, get_response: Callable) -> None` signature and what `get_response` is
- The `__call__(self, request: HttpRequest) -> HttpResponse` signature
- Where in `__call__` to do pre-processing vs post-processing (before and after `get_response(request)`)
- How to check if the user is authenticated before querying
- What to attach to `request` and what to set when unauthenticated
- That it must be registered in `MIDDLEWARE` in settings after `AuthenticationMiddleware`

### views.py

Skeleton: `from __future__ import annotations` header, import placeholders, one class or function stub per view.

Key TODOs to include:
- Whether to use a class-based view or function-based view and why
- Which mixins apply (e.g., `LoginRequiredMixin`) and their import source
- What context variables to pass to the template and where they come from
- Which template to render (using the `templates/<app>/` convention)
- For form views: where form validation logic goes, what happens on success vs failure
- Type hints for all parameters and return types

### forms.py

Skeleton: `from __future__ import annotations` header, import placeholders, one form class stub per form.

Key TODOs to include:
- Whether it's a `Form` or `ModelForm` and which model it binds to
- Which fields to include/exclude in the `Meta` class
- Any custom `clean_<field>` or `clean` methods needed and what they validate
- Widget overrides if the default rendering is wrong for the field type
- Type hints on any custom methods

### apps.py

Skeleton: `from __future__ import annotations` header, existing `AppConfig` class with a `ready()` method stub added.

Key TODOs to include:
- That `ready()` is the correct place to import signals — explain why (avoids circular imports at module load time)
- The exact import pattern to use inside `ready()` (import the signals module, not individual functions)
- A note that `ready()` should only contain signal wiring, not business logic

## After Stubbing

- Provide a brief summary in the chat listing what was stubbed and any open decisions the developer should think about
- Call out any dependencies between files (e.g., "apps.py `ready()` must import signals.py, write signals.py first")
- Reference relevant Django docs sections by name (e.g., "Django signals docs", "Writing middleware")
- Use pseudocode or generic examples in the chat to explain concepts — do not give the exact answer

## Managing Stubs

- Only manage `# TODO(stub): ...` comments — never touch `# TODO: ...` or `# TODO(review): ...` comments
- On subsequent runs, remove TODO(stub) comments for sections the developer has implemented
- Add new TODO(stub) comments if requirements have changed or new context is available
