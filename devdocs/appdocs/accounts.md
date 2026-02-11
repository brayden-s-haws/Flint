# accounts app - MVP Checklist

## Models

- [ ] `Account` — tenant/organization model (name, slug, timestamps)
- [ ] `AccountMembership` — links User to Account with a role (MVP: owner only)

## Admin

- [ ] Register `Account` and `AccountMembership` in admin

## Middleware

- [ ] Tenant middleware — resolves the current account from the logged-in user and attaches to request

## Signals / Hooks

- [ ] Auto-create an Account + owner membership when a new user registers (1:1 for MVP)

## Views

- [ ] None for MVP (account is auto-created, no settings page needed yet)

## Templates

- [ ] None for MVP

## MVP Notes

- Single account per user (1:1) — no team invites, no multi-account switching
- Owner role only — no role-based permissions yet