# Feature: Account Settings Page

**Source:** `devdocs/appdocs/post_mvp.md` — "Account settings page (rename account)"
**Status:** Not started
**Target phase:** Post-MVP Phase 2

---

## Overview

Adds a settings page at `/account/settings/` that lets the account owner rename their account. This is the first user-facing account management screen. It lives in the existing `apps/accounts/` app and requires no new models — just a form, view, URL, and template.

---

## Dependencies

- [x] `apps/accounts/` — `Account` model with `name` field exists
- [x] `TenantMiddleware` — `request.account` is attached on every request
- [x] `LoginRequiredMixin` — available for auth-gating views

---

## Implementation Checklist

### Forms
- [x] `AccountSettingsForm` in `apps/accounts/forms.py` — `ModelForm` for `Account`, exposing only the `name` field; styled widgets via `__init__` (Tailwind classes per CLAUDE.md)

### Views & URLs
- [x] `AccountSettingsView` in `apps/accounts/views.py` — `LoginRequiredMixin` + `UpdateView`; uses `request.account` as the object (not a URL pk); `success_url` redirects back to 
  `accounts:settings`; shows a success message via `django.contrib.messages`
- [x] URL in `apps/accounts/urls.py`: `GET/POST /account/settings/` → `AccountSettingsView`, `name='settings'`
- [x] Include `apps/accounts/urls.py` in `Flint/urls.py` if not already included (currently empty urlpatterns — check whether the include already exists)

### Template
- [x] `templates/accounts/account_settings.html` — extends `base.html`; page heading "Account Settings"; form with labelled `name` field and a Save button; displays `messages` for success/error 
  feedback

---

## Key Design Decisions

- **No URL pk:** The view resolves the object from `request.account` rather than a URL parameter — only the current account owner can edit their own account, so no pk is needed or safe to expose.
- **Owner-only:** Only the account owner should be able to rename the account. Check `request.user == request.account.owner` in the view and return a 403 if not (even if the URL is reached by a non-owner member).
- **Single field:** The form exposes only `name` — no other `Account` fields are editable yet. Future settings (billing, branding, etc.) will extend this page.

---

## Notes

- `apps/accounts/urls.py` currently has empty `urlpatterns` — verify whether the file is already included in `Flint/urls.py`. If not, add the include.
- Nav link to `/account/settings/` should eventually appear in the top nav or user menu, but that can be a follow-on polish task.