# Flint Views Reference

This document details every view needed for the MVP, organized by app. Use this as your blueprint when building views and templates.

---

## Notation Guide

| Symbol | Meaning |
|--------|---------|
| `@login` | Requires authenticated user |
| `@owner` | Requires account owner role |
| `GET` | Read-only request |
| `POST` | Form submission or action |
| `HTMX` | Returns partial HTML for HTMX swap |

---

## App: `core`

### Dashboard

The main landing page after login.

| Attribute | Value |
|-----------|-------|
| **URL** | `/` |
| **Name** | `core:dashboard` |
| **Methods** | GET |
| **Auth** | @login |
| **Template** | `core/dashboard.html` |

**Context:**
```
- sources: List of user's sources (recent 5)
- sources_count: Total source count
- tables_count: Total tables across all sources
- insights_count: Total insights generated
- recent_insights: Last 5 insights
- recent_syncs: Last 5 sync logs
```

**Notes:**
- Redirect here after login
- Show empty state if no sources connected
- Quick links to add source, browse catalog

---

## App: `users`

### Register

Create a new user account.

| Attribute | Value |
|-----------|-------|
| **URL** | `/auth/register/` |
| **Name** | `users:register` |
| **Methods** | GET, POST |
| **Auth** | Anonymous only |
| **Template** | `users/register.html` |

**Form Fields:**
- email (required)
- password (required)
- password_confirm (required)

**POST Success:**
- Create User
- Create Account (auto-named from email domain or "My Workspace")
- Create AccountMembership with role=owner
- Log user in
- Redirect to `core:dashboard`

**Notes:**
- Redirect to dashboard if already logged in
- Consider adding first_name/last_name (optional)

---

### Login

Authenticate existing user.

| Attribute | Value |
|-----------|-------|
| **URL** | `/auth/login/` |
| **Name** | `users:login` |
| **Methods** | GET, POST |
| **Auth** | Anonymous only |
| **Template** | `users/login.html` |

**Form Fields:**
- email (required)
- password (required)
- remember_me (optional checkbox)

**POST Success:**
- Authenticate user
- Set session
- Redirect to `core:dashboard` or `?next=` param

**Notes:**
- Show error on invalid credentials
- Link to register page
- Link to password reset (post-MVP)

---

### Logout

End user session.

| Attribute | Value |
|-----------|-------|
| **URL** | `/auth/logout/` |
| **Name** | `users:logout` |
| **Methods** | POST |
| **Auth** | @login |
| **Template** | None (redirect) |

**POST Success:**
- Clear session
- Redirect to `users:login`

**Notes:**
- Use POST to prevent CSRF issues with logout links
- Can use a simple form with button in navbar

---

### Profile (Post-MVP)

View/edit user profile.

| Attribute | Value |
|-----------|-------|
| **URL** | `/auth/profile/` |
| **Name** | `users:profile` |
| **Methods** | GET, POST |
| **Auth** | @login |
| **Template** | `users/profile.html` |

**Notes:**
- Defer for MVP - focus on core features first

---

## App: `accounts`

### Account Settings

View and edit account details.

| Attribute | Value |
|-----------|-------|
| **URL** | `/account/settings/` |
| **Name** | `accounts:settings` |
| **Methods** | GET, POST |
| **Auth** | @login, @owner |
| **Template** | `accounts/settings.html` |

**Context (GET):**
```
- account: Current account
- members: List of AccountMemberships (post-MVP)
```

**Form Fields:**
- name (account display name)

**POST Success:**
- Update account
- Show success message
- Redirect to same page

**Notes:**
- For MVP, just allow editing account name
- Add member management in post-MVP

---

## App: `sources`

### Source List

Display all connected data sources.

| Attribute | Value |
|-----------|-------|
| **URL** | `/sources/` |
| **Name** | `sources:list` |
| **Methods** | GET |
| **Auth** | @login |
| **Template** | `sources/source_list.html` |

**Context:**
```
- sources: All sources for current account
- source_types: Available connector types (for "Add" dropdown)
```

**Notes:**
- Show empty state with CTA to add first source
- Display last sync status and time for each source
- Link to source detail

---

### Source Create

Connect a new data source.

| Attribute | Value |
|-----------|-------|
| **URL** | `/sources/add/<slug:source_type>/` |
| **Name** | `sources:create` |
| **Methods** | GET, POST |
| **Auth** | @login |
| **Template** | `sources/source_form.html` |

**URL Parameters:**
- source_type: Slug of SourceType (e.g., "postgresql")

**Context (GET):**
```
- source_type: The SourceType object
- form: Source creation form
- credential_fields: Dynamic fields based on source_type.config_schema
```

**Form Fields:**
- name (user-given name, required)
- description (optional)
- Dynamic credential fields based on source type:
  - PostgreSQL: host, port, database, username, password, ssl_mode
  - HubSpot: api_key (post-MVP)

**POST Success:**
- Validate form
- Encrypt credentials
- Create Source
- Redirect to `sources:detail` with success message

**Notes:**
- Dynamic form based on source type
- Show connection requirements/help text
- Consider "Test before save" button (HTMX)

---

### Source Detail

View source details, schemas, and tables.

| Attribute | Value |
|-----------|-------|
| **URL** | `/sources/<int:pk>/` |
| **Name** | `sources:detail` |
| **Methods** | GET |
| **Auth** | @login |
| **Template** | `sources/source_detail.html` |

**Context:**
```
- source: The Source object
- schemas: List of schemas for this source
- tables_count: Total tables across schemas
- columns_count: Total columns
- insights_count: Insights for this source's objects
- recent_syncs: Last 5 SourceSyncLog entries
- last_sync: Most recent sync log
```

**Notes:**
- Main hub for a connected source
- Show sync status prominently
- Actions: Edit, Sync Now, Test Connection, Delete
- List schemas with table counts

---

### Source Edit

Edit source settings (name, description).

| Attribute | Value |
|-----------|-------|
| **URL** | `/sources/<int:pk>/edit/` |
| **Name** | `sources:edit` |
| **Methods** | GET, POST |
| **Auth** | @login |
| **Template** | `sources/source_form.html` |

**Form Fields:**
- name (required)
- description (optional)
- Credential fields (show as password fields, optional - only update if provided)

**POST Success:**
- Update source
- Re-encrypt credentials if changed
- Redirect to `sources:detail`

**Notes:**
- Reuse source_form.html template with edit context
- Don't show existing password values (security)
- "Leave blank to keep current" for credential fields

---

### Source Delete

Delete a source and all its metadata.

| Attribute | Value |
|-----------|-------|
| **URL** | `/sources/<int:pk>/delete/` |
| **Name** | `sources:delete` |
| **Methods** | GET, POST |
| **Auth** | @login, @owner |
| **Template** | `sources/source_confirm_delete.html` |

**Context (GET):**
```
- source: The Source object
- tables_count: How many tables will be deleted
- insights_count: How many insights will be deleted
```

**POST Success:**
- Delete source (cascades to schemas, tables, columns, insights)
- Redirect to `sources:list` with success message

**Notes:**
- Show clear warning about what will be deleted
- Require typing source name to confirm (optional, good UX)

---

### Source Test Connection (HTMX)

Test if source credentials work.

| Attribute | Value |
|-----------|-------|
| **URL** | `/sources/<int:pk>/test/` |
| **Name** | `sources:test_connection` |
| **Methods** | POST |
| **Auth** | @login |
| **Template** | `sources/_connection_status.html` (partial) |

**Response (HTMX partial):**
```html
<!-- Success -->
<div class="text-green-600">Connected successfully</div>

<!-- Failure -->
<div class="text-red-600">Connection failed: {error_message}</div>
```

**Notes:**
- Called via HTMX from source detail page
- Returns partial HTML to swap into status area
- Decrypt credentials, attempt connection, return result

---

### Source Sync (HTMX)

Trigger metadata sync for a source.

| Attribute | Value |
|-----------|-------|
| **URL** | `/sources/<int:pk>/sync/` |
| **Name** | `sources:sync` |
| **Methods** | POST |
| **Auth** | @login |
| **Template** | `sources/_sync_status.html` (partial) |

**Process:**
1. Create SourceSyncLog with status=running
2. Connect to source
3. Discover schemas, tables, columns
4. Create/update catalog models
5. Update SourceSyncLog with counts and status

**Response (HTMX partial):**
```html
<!-- During sync (if async) -->
<div>Syncing... <span class="spinner"></span></div>

<!-- Complete -->
<div>Sync complete: {tables_count} tables, {columns_count} columns</div>
```

**Notes:**
- For MVP, run synchronously (may take a few seconds)
- Update UI with results via HTMX
- Post-MVP: Use Celery for background sync

---

## App: `catalog`

### Schema Detail

View tables within a schema.

| Attribute | Value |
|-----------|-------|
| **URL** | `/catalog/schemas/<int:pk>/` |
| **Name** | `catalog:schema_detail` |
| **Methods** | GET |
| **Auth** | @login |
| **Template** | `catalog/schema_detail.html` |

**Context:**
```
- schema: The Schema object
- source: Parent source
- tables: Tables in this schema (exclude system tables)
- tables_count: Total table count
```

**Notes:**
- Link from source detail page
- List tables with row counts, last insight date
- Filter: show/hide system tables

---

### Table List

Browse all tables across sources.

| Attribute | Value |
|-----------|-------|
| **URL** | `/catalog/tables/` |
| **Name** | `catalog:table_list` |
| **Methods** | GET |
| **Auth** | @login |
| **Template** | `catalog/table_list.html` |

**Query Parameters:**
- `source`: Filter by source ID
- `schema`: Filter by schema ID
- `q`: Search table names
- `has_insight`: Filter to tables with/without insights

**Context:**
```
- tables: Filtered/paginated table list
- sources: For filter dropdown
- schemas: For filter dropdown (filtered by selected source)
- query: Current search query
- filters: Current filter state
```

**Notes:**
- Global table browser across all sources
- Useful for searching across the catalog
- Pagination (20-50 per page)

---

### Table Detail

View table metadata, columns, and insights.

| Attribute | Value |
|-----------|-------|
| **URL** | `/catalog/tables/<int:pk>/` |
| **Name** | `catalog:table_detail` |
| **Methods** | GET |
| **Auth** | @login |
| **Template** | `catalog/table_detail.html` |

**Context:**
```
- table: The Table object
- schema: Parent schema
- source: Parent source
- columns: All columns for this table (ordered by ordinal_position)
- primary_keys: Columns that are PKs
- foreign_keys: Columns that are FKs with their targets
- insights: All insights targeting this table
- has_description: Boolean - does table have a description insight?
```

**Notes:**
- Main view for understanding a table
- Show columns in a data grid
- Highlight PKs and FKs visually
- "Generate Description" button if no insight exists
- Display existing insights prominently

---

### Column Detail (Optional)

View column details and insights.

| Attribute | Value |
|-----------|-------|
| **URL** | `/catalog/columns/<int:pk>/` |
| **Name** | `catalog:column_detail` |
| **Methods** | GET |
| **Auth** | @login |
| **Template** | `catalog/column_detail.html` |

**Context:**
```
- column: The Column object
- table: Parent table
- insights: Insights targeting this column
- foreign_key_target: Referenced table/column if FK
- referenced_by: Other columns that reference this one
```

**Notes:**
- May not be needed for MVP
- Could show column info in modal from table detail instead
- Useful when column-level insights become common

---

## App: `insights`

### Insight List

View all generated insights.

| Attribute | Value |
|-----------|-------|
| **URL** | `/insights/` |
| **Name** | `insights:list` |
| **Methods** | GET |
| **Auth** | @login |
| **Template** | `insights/insight_list.html` |

**Query Parameters:**
- `type`: Filter by insight_type (description, usage, etc.)
- `source`: Filter by source
- `approved`: Filter by approval status
- `q`: Search insight content

**Context:**
```
- insights: Filtered/paginated insight list
- insight_types: For filter dropdown
- sources: For filter dropdown
- filters: Current filter state
```

**Notes:**
- Show insight title/preview, target, type, date
- Link to insight detail or target (table detail)
- Quick approve/unapprove toggle (HTMX)

---

### Insight Detail

View a single insight.

| Attribute | Value |
|-----------|-------|
| **URL** | `/insights/<int:pk>/` |
| **Name** | `insights:detail` |
| **Methods** | GET |
| **Auth** | @login |
| **Template** | `insights/insight_detail.html` |

**Context:**
```
- insight: The Insight object
- targets: InsightTarget objects with resolved source/table/column
- prompt: The InsightPrompt used (if LLM-generated)
- created_by: User who created/triggered
```

**Notes:**
- Full insight content with markdown rendering
- Show metadata: type, source (LLM/manual), model used, tokens
- Links to all targets
- Approve/edit/delete actions

---

### Generate Insight (HTMX)

Generate an LLM insight for a target.

| Attribute | Value |
|-----------|-------|
| **URL** | `/insights/generate/` |
| **Name** | `insights:generate` |
| **Methods** | POST |
| **Auth** | @login |
| **Template** | `insights/_generated_insight.html` (partial) |

**POST Data:**
- `target_type`: "table" or "column"
- `target_id`: ID of the target object
- `insight_type`: Type of insight to generate (default: "description")

**Process:**
1. Load target object (table or column)
2. Gather context (column names, types, sample relationships)
3. Load active InsightPrompt for insight_type
4. Call LLM API with formatted prompt
5. Create Insight and InsightTarget
6. Return rendered insight partial

**Response (HTMX partial):**
```html
<div class="insight-card">
  <h3>Generated Description</h3>
  <div class="insight-content">{rendered_markdown}</div>
  <div class="insight-meta">Generated by {model} | {token_count} tokens</div>
  <button hx-post="/insights/{id}/approve/">Approve</button>
</div>
```

**Notes:**
- Called from table detail page
- Show loading spinner during generation
- Handle LLM API errors gracefully
- Consider rate limiting

---

### Approve Insight (HTMX)

Mark an insight as approved.

| Attribute | Value |
|-----------|-------|
| **URL** | `/insights/<int:pk>/approve/` |
| **Name** | `insights:approve` |
| **Methods** | POST |
| **Auth** | @login |
| **Template** | `insights/_approval_badge.html` (partial) |

**POST Success:**
- Set insight.is_approved = True
- Set insight.approved_by = request.user
- Set insight.approved_at = now

**Response (HTMX partial):**
```html
<span class="badge badge-green">Approved by {user} on {date}</span>
```

**Notes:**
- Quick toggle without full page reload
- Also support unapprove action

---

### Edit Insight

Edit insight content manually.

| Attribute | Value |
|-----------|-------|
| **URL** | `/insights/<int:pk>/edit/` |
| **Name** | `insights:edit` |
| **Methods** | GET, POST |
| **Auth** | @login |
| **Template** | `insights/insight_form.html` |

**Form Fields:**
- title (optional)
- content (required, textarea with markdown preview)
- insight_type (select)

**POST Success:**
- Update insight
- Mark source_type as "manual" if was "llm"
- Redirect to insight detail

**Notes:**
- Allow users to refine LLM outputs
- Track that it was manually edited

---

### Delete Insight

Delete an insight.

| Attribute | Value |
|-----------|-------|
| **URL** | `/insights/<int:pk>/delete/` |
| **Name** | `insights:delete` |
| **Methods** | POST |
| **Auth** | @login |
| **Template** | None (redirect) |

**POST Success:**
- Delete insight and its targets
- Redirect to `insights:list` or previous page

**Notes:**
- Consider soft delete (is_deleted flag) for audit
- Can use HTMX to remove from list without reload

---

## URL Configuration Summary

### Main urls.py

```python
# Flint/urls.py
from django.contrib import admin
from django.urls import path, include

urlpatterns = [
    path('admin/', admin.site.urls),
    path('', include('apps.core.urls')),
    path('auth/', include('apps.users.urls')),
    path('account/', include('apps.accounts.urls')),
    path('sources/', include('apps.sources.urls')),
    path('catalog/', include('apps.catalog.urls')),
    path('insights/', include('apps.insights.urls')),
]
```

### App URL Files

**apps/core/urls.py**
```
/                          -> core:dashboard
```

**apps/users/urls.py**
```
/auth/register/            -> users:register
/auth/login/               -> users:login
/auth/logout/              -> users:logout
```

**apps/accounts/urls.py**
```
/account/settings/         -> accounts:settings
```

**apps/sources/urls.py**
```
/sources/                  -> sources:list
/sources/add/<slug>/       -> sources:create
/sources/<pk>/             -> sources:detail
/sources/<pk>/edit/        -> sources:edit
/sources/<pk>/delete/      -> sources:delete
/sources/<pk>/test/        -> sources:test_connection
/sources/<pk>/sync/        -> sources:sync
```

**apps/catalog/urls.py**
```
/catalog/schemas/<pk>/     -> catalog:schema_detail
/catalog/tables/           -> catalog:table_list
/catalog/tables/<pk>/      -> catalog:table_detail
/catalog/columns/<pk>/     -> catalog:column_detail  (optional)
```

**apps/insights/urls.py**
```
/insights/                 -> insights:list
/insights/<pk>/            -> insights:detail
/insights/generate/        -> insights:generate
/insights/<pk>/approve/    -> insights:approve
/insights/<pk>/edit/       -> insights:edit
/insights/<pk>/delete/     -> insights:delete
```

---

## View Implementation Pattern

Use class-based views for CRUD, function-based for simple actions.

### Standard CRUD Pattern

```python
# apps/sources/views.py
from django.views.generic import ListView, DetailView, CreateView, UpdateView, DeleteView
from django.contrib.auth.mixins import LoginRequiredMixin
from django.urls import reverse_lazy
from .models import Source

class SourceListView(LoginRequiredMixin, ListView):
    model = Source
    template_name = 'sources/source_list.html'
    context_object_name = 'sources'

    def get_queryset(self):
        # Filter to current account only
        return Source.objects.filter(account=self.request.user.account)
```

### HTMX Action Pattern

```python
# apps/sources/views.py
from django.contrib.auth.decorators import login_required
from django.views.decorators.http import require_POST
from django.shortcuts import get_object_or_404
from django.http import HttpResponse
from django.template.loader import render_to_string

@login_required
@require_POST
def sync_source(request, pk):
    source = get_object_or_404(Source, pk=pk, account=request.user.account)

    # Run sync logic...
    result = source.run_sync()

    # Return partial HTML for HTMX
    html = render_to_string('sources/_sync_status.html', {
        'source': source,
        'result': result,
    }, request=request)

    return HttpResponse(html)
```

---

## Authentication Mixins

### Account Access Mixin

Create this in `apps/core/mixins.py`:

```python
class AccountRequiredMixin:
    """Ensures user has access to current account."""

    def dispatch(self, request, *args, **kwargs):
        if not hasattr(request.user, 'account'):
            # Handle user without account
            return redirect('accounts:setup')
        return super().dispatch(request, *args, **kwargs)

class AccountOwnerRequiredMixin(AccountRequiredMixin):
    """Ensures user is owner of current account."""

    def dispatch(self, request, *args, **kwargs):
        # Check membership role
        membership = request.user.memberships.filter(
            account=request.user.account
        ).first()
        if not membership or membership.role != 'owner':
            raise PermissionDenied
        return super().dispatch(request, *args, **kwargs)
```

---

## MVP Views Only

For MVP, implement these views first:

| Priority | App | Views |
|----------|-----|-------|
| 1 | users | register, login, logout |
| 2 | core | dashboard |
| 3 | sources | list, create (PostgreSQL only), detail, test_connection, sync |
| 4 | catalog | table_list, table_detail |
| 5 | insights | generate, list, detail |

**Defer:**
- source edit/delete (can use Django admin)
- column_detail
- insight edit/delete/approve
- account settings
- schema_detail (show tables on source detail instead)