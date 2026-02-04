# CLAUDE.md

This file provides guidance to Claude Code (claude.ai/code) when working with code in this repository.

## Project Overview

Luminetiq is a data intelligence platform that inspects databases and APIs to generate metadata insights without storing actual data. It's in the data catalog/observability space but focused on **intelligence generation** rather than just cataloging.

- **Framework**: Django 6.0.2, Python 3.13.5
- **Frontend**: Django templates + HTMX (server-rendered)
- **LLM**: OpenAI + Anthropic with provider abstraction
- **Team**: Solo developer (keep architecture simple)

See `docs/architecture.md` for full architecture details and `docs/potential_features.md` for future feature ideas.

## Common Commands

```bash
# Activate virtual environment
source .venv/bin/activate

# Run development server
python manage.py runserver

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
- **Luminetiq/**: Main Django project configuration (settings, urls, wsgi/asgi)
- **templates/**: Project-wide templates directory
- **docs/**: Architecture and planning documentation
- **manage.py**: Django management CLI entry point

### Planned Apps Structure (in apps/ directory)
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

## Configuration Notes

- Database: SQLite3 (development) at `db.sqlite3`
- Admin interface available at `/admin/`
- Templates configured to use `templates/` directory at project root
- Static files use Django defaults (`STATIC_URL = 'static/'`)

## Environment Variables

All application credentials and secrets are stored in `.env` (not committed). Copy `.env.example` to `.env` for local development.

Current variables:
- `SECRET_KEY`: Django secret key (required)
- `DEBUG`: Enable debug mode (default: False)

Planned additions:
- `OPENAI_API_KEY`: OpenAI API key for LLM insights
- `ANTHROPIC_API_KEY`: Anthropic API key for LLM insights
- `ENCRYPTION_KEY`: Fernet key for credential encryption
- `DATABASE_URL`: PostgreSQL connection (production)

Add new credentials to `.env` and access via `os.getenv('VAR_NAME')` in settings.py. Customer database credentials are stored encrypted in the database, not in `.env`.

## MVP Scope

The MVP focuses on validating the core value proposition:
1. User registration/login (email-based)
2. Connect PostgreSQL sources with encrypted credentials
3. Sync metadata (schemas, tables, columns)
4. Generate LLM table descriptions
5. Browse and view insights

See `docs/architecture.md` for full MVP scope and phased roadmap.
