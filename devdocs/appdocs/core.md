# core app - MVP Checklist

## Models

- [x] `TimeStampedModel` — abstract model with `created_at`, `updated_at`
- [x] `TenantAwareModel` — abstract model extending `TimeStampedModel` with `account` FK

## Mixins

- [x] `TenantQuerysetMixin` — view mixin that filters querysets by the current user's account

## Templates

- [x] `base.html` — base template with nav, messages, block structure (project-level `templates/`)
- [x] `components/_navbar.html` — navigation partial
- [ ] `components/_messages.html` — flash messages partial
- [ ] `core/dashboard.html` — logged-in landing page / dashboard

## Views

- [ ] Dashboard view (homepage after login, shows overview of sources/tables) @login_required needed

## URLs

- [ ] `/` — dashboard (redirects to login if not authenticated)