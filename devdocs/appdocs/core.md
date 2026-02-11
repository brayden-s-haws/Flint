# core app - MVP Checklist

## Models

- [ ] `TimeStampedModel` — abstract model with `created_at`, `updated_at`
- [ ] `TenantAwareModel` — abstract model extending `TimeStampedModel` with `account` FK

## Mixins

- [ ] `TenantQuerysetMixin` — view mixin that filters querysets by the current user's account

## Templates

- [ ] `base.html` — base template with nav, messages, block structure (project-level `templates/`)
- [ ] `components/_navbar.html` — navigation partial
- [ ] `components/_messages.html` — flash messages partial
- [ ] `core/dashboard.html` — logged-in landing page / dashboard

## Views

- [ ] Dashboard view (homepage after login, shows overview of sources/tables)

## URLs

- [ ] `/` — dashboard (redirects to login if not authenticated)