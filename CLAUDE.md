# CLAUDE.md

This file provides guidance to Claude Code (claude.ai/code) when working with code in this repository.

## Working Style

**Act as a coach, not a coder.** Guide me through building features rather than writing the code for me.

- Provide pseudocode, examples, and explanations
- Point me to relevant documentation and patterns
- Review my code and suggest improvements
- Help debug issues by asking questions and guiding my thinking
- Break down complex tasks into manageable steps
- Let me do the heavy lifting - I learn by doing

**Frontend guidance exception:** For HTML templates, Tailwind CSS, and HTMX, provide more detailed directions than for backend code. Still don't write the actual implementation, but you can:
- Name specific Django template tags, Tailwind utility classes, and HTMX attributes to use
- Describe the structure and layout in detail (e.g., "a flex container with two children")
- Provide pseudocode or generic examples in the chat (not in the file)
- Use the `/stub-ui` skill to scaffold template files with detailed TODO comments

## Project Overview

Flint is a data intelligence platform that inspects databases and APIs to generate metadata insights without storing actual data. It's in the data catalog/observability space but focused on **intelligence generation** rather than just cataloging.

- **Framework**: Django 6.0.2, Python 3.13.5
- **Frontend**: Django templates + HTMX (server-rendered)
- **LLM**: OpenAI + Anthropic with provider abstraction
- **Team**: Solo developer (keep architecture simple)

See `devdocs/architecture.md` for full architecture details and `devdocs/potential_features.md` for future feature ideas.

## Common Commands

```bash
# Activate virtual environment
source .venv/bin/activate

# Run development server
python manage.py runserver

# Watch and rebuild Tailwind CSS in dev (run in a second terminal alongside runserver)
npm run watch:css

# One-shot Tailwind build (minified — use before deploys or after pulling changes)
npm run build:css

# Run migrations
python manage.py migrate

# Create new migrations after model changes
python manage.py makemigrations

# Create a new Django app (place in apps/ directory)
cd apps && python ../manage.py startapp <app_name>

# Run tests
python manage.py test

# Run a single test module
python manage.py test apps.<app_name>.tests.<TestClass>

# Create superuser for admin access
python manage.py createsuperuser

# Django shell
python manage.py shell
```

## Architecture

### Current State
- **Flint/**: Main Django project configuration (settings, urls, wsgi/asgi)
- **templates/**: Project-wide templates directory
- **devdocs/**: Developer documentation (architecture, models, views, getting started)
- **manage.py**: Django management CLI entry point

### Apps Structure (in apps/ directory)
- **core/**: Shared utilities, base models (TimeStampedModel, TenantAwareModel), tenant middleware
- **accounts/**: Multi-tenancy - Account, AccountMembership models
- **users/**: Custom User model with email-based auth
- **sources/**: Data source connections, connector plugin system
- **catalog/**: Schema, Table, Column metadata models
- **insights/**: LLM-generated insights, provider abstraction

### Key Patterns
- **Multi-tenancy**: Shared database with `account` foreign key on all tenant-scoped models
- **Connectors**: Hybrid approach using PyAirbyte (300+ sources) + native connectors for deep metadata extraction
- **LLM abstraction**: Provider layer supporting both OpenAI and Anthropic
- **Credential encryption**: Fernet encryption for stored database credentials

## Code Standards

### Type Hints

**All code must use type hints.** This is a strict requirement throughout the project.

- All function parameters and return types must be annotated
- Use `from __future__ import annotations` at the top of each module for modern syntax
- Use `typing` module imports as needed (`Optional`, `List`, `Dict`, `Any`, etc.)
- Django-specific: use `django-stubs` types where applicable

When reviewing code, flag any missing type hints.

**Examples:**
```python
from __future__ import annotations
from typing import Optional

def get_user_by_email(email: str) -> Optional[User]:
    ...

def process_sources(sources: list[Source], limit: int = 10) -> dict[str, int]:
    ...
```

### Forms

**Every new form must include styled widgets.** Add an `__init__` method that applies Tailwind classes to all fields via `widget.attrs.update()`.

Input classes: `w-full bg-flint-card border border-flint-border-em rounded-md px-3 py-2 text-sm text-flint-text focus:outline-none focus:ring-2 focus:ring-flint-orange`

Label classes (in templates): `block text-sm font-medium text-flint-muted mb-1`

```python
def __init__(self, *args, **kwargs):
    super().__init__(*args, **kwargs)
    for field in self.fields.values():
        field.widget.attrs.update({'class': 'w-full bg-flint-card border border-flint-border-em rounded-md px-3 py-2 text-sm text-flint-text focus:outline-none focus:ring-2 focus:ring-flint-orange'})
```

Note: `ModelChoiceField` renders as `<select>` — the classes apply but may need `appearance-none` added if the browser's native styling bleeds through.

## Configuration Notes

- Database: SQLite3 (development) at `db.sqlite3`
- Admin interface available at `/admin/`
- Templates configured to use `templates/` directory at project root
- Static files use Django defaults (`STATIC_URL = 'static/'`)
- **Tailwind CSS:** config in `tailwind.config.js` (project root); custom CSS source in `static/css/input.css`; compiled output in `static/css/output.css` (committed). `base.html` loads only the compiled `output.css` — do not put colors, fonts, or custom rules back into `base.html`. Add new colors to `tailwind.config.js`, custom rules to `input.css`, then run `npm run build:css` (or keep `npm run watch:css` running).

## Environment Variables

All application credentials and secrets are stored in `.env` (not committed). Copy `.env.example` to `.env` for local development.

Current variables:
- `SECRET_KEY`: Django secret key (required)
- `DEBUG`: Enable debug mode (default: False)
- `OPENAI_API_KEY`: OpenAI API key for LLM insights
- `ANTHROPIC_API_KEY`: Anthropic API key for LLM insights
- `ENCRYPTION_KEY`: Fernet key for credential encryption
- `DATABASE_URL`: PostgreSQL connection (production)

Add new credentials to `.env` and access via `os.getenv('VAR_NAME')` in settings.py. Customer database credentials are stored encrypted in the database, not in `.env`.

## Current Status

**MVP is complete.** All five core features are built and working:
1. User registration/login (email-based)
2. Connect PostgreSQL sources with encrypted credentials
3. Sync metadata (schemas, tables, columns)
4. Generate LLM table descriptions
5. Browse and view insights

Active work is now post-MVP. See:
- `devdocs/ui/cleanup.md` — UI polish backlog
- `devdocs/appdocs/post_mvp.md` — Phase 2 feature backlog
- `devdocs/architecture.md` for full architecture and phased roadmap
