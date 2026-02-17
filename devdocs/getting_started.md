# Getting Started: Building Luminetiq MVP

This guide walks you through building the Luminetiq MVP step by step. Think of this as your tech lead's onboarding doc.

---

## Prerequisites Checklist

Before writing any code, make sure you have:

- [x] Python 3.13+ installed
- [x] Virtual environment created and activated (`.venv/`)
- [x] `.env` file created from `.env.example`
- [x] Django installed (`pip install django`)
- [x] Dev server runs without errors: `python manage.py runserver`

**Do NOT run `python manage.py migrate` yet.** You must create the custom User model first (Step 1 below). Running migrations before defining your custom User model will cause Django to create its default auth tables, and you'll need to reset the database to fix it.

---

## App Build Order

**This order matters.** Each app builds on the ones before it.

### 1. `users` (FIRST - Critical) DONE!

**Why first?** Django's custom User model must be defined before ANY migrations are run. If you've already run `migrate`, you'll need to reset the database.

**What it provides:**
- Custom User model with email-based authentication
- No username field (email is the identifier)

**Depends on:** Nothing

**Already ran `migrate`? Here's the fix:**

If you ran `python manage.py migrate` before creating the custom User model, Django already created its default `auth_user` table. To start fresh:

1. Delete `db.sqlite3` from the project root
2. Delete any `migrations/` files in your apps (keep the `__init__.py` files)
3. Build the `users` app and define the custom User model (see "Custom User Model Setup" below)
4. Set `AUTH_USER_MODEL` in `settings.py`
5. Run `python manage.py makemigrations users`
6. Run `python manage.py migrate`

Django will create a new `db.sqlite3` automatically when you run `migrate`. No data is lost since this is a fresh dev database.

---

### 2. `core` DONE

**Why second?** Provides base models and utilities that all other apps inherit from.

**What it provides:**
- `TimeStampedModel` - abstract model with `created_at`, `updated_at`
- `TenantAwareModel` - abstract model with `account` foreign key
- Shared utilities and mixins

**Depends on:** Nothing (but users should exist first for the User FK patterns)

---

### 3. `accounts` DONE

**Why third?** Multi-tenancy foundation. All data is scoped to accounts.

**What it provides:**
- `Account` model (the tenant/organization)
- `AccountMembership` linking users to accounts with roles
- Middleware for resolving current account from request

**Depends on:** `users`, `core`

---

### 4. `sources` DONE

**What it provides:**
- `SourceType` registry of supported connectors
- `Source` model for connected data sources (encrypted credentials)
- `SourceSyncLog` for sync history
- Connector plugin system (start with PostgreSQL)

**Depends on:** `accounts`, `core`

---

### 5. `catalog` DONE

**What it provides:**
- `Schema`, `Table`, `Column` models (metadata, NOT actual data)
- `TableStatistics` for row counts, etc.

**Depends on:** `sources`, `core`

---

### 6. `insights`

**What it provides:**
- `Insight` model for LLM-generated content
- `InsightTarget` polymorphic linking to sources/tables/columns
- `InsightPrompt` for versioned prompts
- LLM provider abstraction (OpenAI/Anthropic)

**Depends on:** `catalog`, `sources`, `core`

---

### 7. `api` (Post-MVP)

REST API layer. Skip for MVP - build when you need external integrations.

---

## Creating a New App

Apps live in the `apps/` directory, not the project root.

### Step 1: Create the app

```bash
# Make sure you're in the project root (where manage.py is)
cd apps
python ../manage.py startapp <app_name>
cd ..
```

This creates the standard Django app structure:
```
apps/<app_name>/
├── __init__.py
├── admin.py
├── apps.py
├── migrations/
│   └── __init__.py
├── models.py
├── tests.py
└── views.py
```

### Step 2: Fix the app config

Open `apps/<app_name>/apps.py` and update the `name` to include the `apps.` prefix:

```python
# Before (auto-generated)
class UsersConfig(AppConfig):
    name = 'users'

# After (corrected)
class UsersConfig(AppConfig):
    name = 'apps.users'  # <-- Add apps. prefix
    label = 'users'      # <-- Add this to keep migrations clean
```

### Step 3: Register in INSTALLED_APPS

Open `Luminetiq/settings.py` and add to `INSTALLED_APPS`:

```python
INSTALLED_APPS = [
    'django.contrib.admin',
    'django.contrib.auth',
    # ... other django apps ...

    # Your apps
    'apps.users',
    'apps.core',
    'apps.accounts',
    # ... add as you build them
]
```

### Step 4: Create the app's urls.py

Each app needs its own `urls.py` file (not created by startapp):

```python
# apps/<app_name>/urls.py
from django.urls import path
from . import views

app_name = '<app_name>'  # Enables namespaced URLs like {% url 'users:login' %}

urlpatterns = [
    # Add your URL patterns here
]
```

---

## URL Structure with include()

The main `Luminetiq/urls.py` should use `include()` to delegate to each app's URLs.

### Pattern

```python
# Luminetiq/urls.py
from django.contrib import admin
from django.urls import path, include

urlpatterns = [
    path('admin/', admin.site.urls),

    # App URLs
    path('', include('apps.core.urls')),           # Homepage, dashboard
    path('auth/', include('apps.users.urls')),     # Login, logout, register
    path('account/', include('apps.accounts.urls')), # Account settings
    path('sources/', include('apps.sources.urls')),  # Data sources CRUD
    path('catalog/', include('apps.catalog.urls')),  # Browse tables/columns
    path('insights/', include('apps.insights.urls')), # View/generate insights
]
```

### Naming Conventions

| App | URL Prefix | Why |
|-----|-----------|-----|
| `core` | `/` (root) | Homepage, dashboard live here |
| `users` | `/auth/` | Authentication flows (login, logout, register) |
| `accounts` | `/account/` | Account/org management |
| `sources` | `/sources/` | CRUD for data source connections |
| `catalog` | `/catalog/` | Browsing schemas/tables/columns |
| `insights` | `/insights/` | Viewing and generating insights |

### Using Namespaced URLs in Templates

With `app_name` set in each urls.py, use namespaced URLs:

```html
<!-- In templates -->
<a href="{% url 'users:login' %}">Login</a>
<a href="{% url 'sources:list' %}">My Sources</a>
<a href="{% url 'catalog:table_detail' table.id %}">View Table</a>
```

---

## Custom User Model Setup (Critical) DONE

**Do this BEFORE running any migrations beyond the initial Django setup.**

### Step 1: Create the users app first

```bash
cd apps && python ../manage.py startapp users && cd ..
```

### Step 2: Define the User model

```python
# apps/users/models.py
from __future__ import annotations

from django.contrib.auth.models import AbstractUser
from django.db import models


class User(AbstractUser):
    username = None  # Remove the username field
    email = models.EmailField(unique=True)

    USERNAME_FIELD = 'email'
    REQUIRED_FIELDS = []

    def __str__(self) -> str:
        return self.email
```

### Step 3: Tell Django to use your custom User

Add to `Luminetiq/settings.py`:

```python
AUTH_USER_MODEL = 'users.User'
```

### Step 4: Create and run migrations

```bash
python manage.py makemigrations users
python manage.py migrate
```

---

## Base Models Pattern DONE

Create these in `apps/core/models.py` for other apps to inherit:

```python
# apps/core/models.py
from django.db import models

class TimeStampedModel(models.Model):
    """Abstract base model with created/updated timestamps."""
    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)

    class Meta:
        abstract = True

class TenantAwareModel(TimeStampedModel):
    """Abstract base model scoped to an account (tenant)."""
    account = models.ForeignKey(
        'accounts.Account',
        on_delete=models.CASCADE,
        related_name='%(class)ss'  # e.g., account.sources, account.tables
    )

    class Meta:
        abstract = True
```

Then in other apps:

```python
# apps/sources/models.py
from apps.core.models import TenantAwareModel

class Source(TenantAwareModel):
    name = models.CharField(max_length=255)
    # ... other fields
    # Automatically has: account, created_at, updated_at
```

---

## Template Structure

Templates go in the project-level `templates/` directory:

```
templates/
├── base.html                    # Base template all others extend
├── components/                  # Reusable HTMX components
│   ├── _navbar.html
│   └── _messages.html
├── users/                       # Users app templates
│   ├── login.html
│   └── register.html
├── sources/                     # Sources app templates
│   ├── source_list.html
│   └── source_form.html
└── catalog/                     # Catalog app templates
    ├── table_list.html
    └── table_detail.html
```

In views, reference as:
```python
return render(request, 'users/login.html', context)
```

---

## Workflow for Each App

When building each app, follow this sequence:

1. **Create the app** (startapp command)
2. **Fix apps.py** (add `apps.` prefix to name)
3. **Add to INSTALLED_APPS** in settings.py
4. **Create urls.py** in the app
5. **Add include()** in main urls.py
6. **Define models** in models.py
7. **Create migrations** (`makemigrations <app_name>`)
8. **Run migrations** (`migrate`)
9. **Register models in admin.py** (for easy debugging)
10. **Write views** in views.py
11. **Create templates** in templates/<app_name>/
12. **Wire up URLs** in the app's urls.py
13. **Run code review** — invoke `/code-review <file_path>` to review your work before testing
14. **Test manually** in browser

---

## Git Workflow: Branching, Merging, Cleanup

Each app gets its own feature branch. Build it, verify it works, merge to main, delete the branch, then start the next one.

### Create a branch for a new app

```bash
git checkout main
git checkout -b feature/<app-name>-app
```

### Commit your work

```bash
git add <files>
git commit -m "Add <app-name> app with models and admin"
```

### Merge into main

```bash
git checkout main
git merge feature/<app-name>-app
```

### Delete the branch (after merging)

Local:
```bash
git branch -d feature/<app-name>-app
```

Remote (if you pushed the branch to GitHub):
```bash
git push origin --delete feature/<app-name>-app
```
Or delete it via the GitHub UI under "branches."

### Start the next app

```bash
git checkout -b feature/<next-app>-app
```

---

## Development Tips

### Use the Django Admin Early
Register your models in `admin.py` immediately. It gives you a free CRUD interface for testing without building views.

```python
# apps/sources/admin.py
from django.contrib import admin
from .models import Source, SourceType

admin.site.register(Source)
admin.site.register(SourceType)
```

### Run Migrations Frequently
After any model change:
```bash
python manage.py makemigrations
python manage.py migrate
```

### Use Django Shell for Testing
```bash
python manage.py shell
```
```python
from apps.users.models import User
from apps.sources.models import Source
# Test your models, create objects, verify relationships
```

### Check for Migration Issues
If you see migration conflicts or errors:
```bash
python manage.py showmigrations  # See what's applied
python manage.py migrate --plan  # See what would run
```

---

## Next Steps

1. Read `devdocs/architecture.md` for the full picture
2. Create a new branch for each app (e.g., `git checkout -b feature/users-app`). Build the app, get it working, then merge back to `main` before starting the next one.
3. Start with the `users` app (custom User model)
4. Build one app at a time, verifying each works before moving on
5. Refer back to this doc when creating new apps

Good luck! You've got this.

---

## Post-Model Build Order: Views, Templates, and Features

Once all app models are in place, go back through each app's `devdocs/appdocs/<app>.md` checklist and build out the remaining items (views, templates, URLs, etc.) in this order:

1. **Base template** — `templates/base.html` with nav, messages, block structure. Every page extends this, so it comes first.
2. **Users** — registration, login, logout views + templates. Auth must work before anything else is usable.
3. **Accounts** — tenant middleware + signal to auto-create an Account when a user registers.
4. **Core** — `TenantQuerysetMixin` + dashboard view. Depends on accounts middleware being in place.
5. **Sources** — CRUD views, PostgreSQL connector, Fernet encryption. This is the main feature.
6. **Catalog** — table list and detail views. Data is populated by source sync.
7. **Insights** — LLM provider abstraction, generate/view insights. The capstone feature.