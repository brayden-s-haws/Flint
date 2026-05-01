# Feature: Domain-Based Registration Guard + Team Invites

**Source:** `devdocs/appdocs/post_mvp.md` — "Domain-based registration guard" and "Team invites"
**Status:** Phase 1 & 2 complete
**Target phase:** Post-MVP Phase 2

---

## Overview

Two closely related features that control how users join Flint:

1. **Domain-based registration guard** — during public registration, check whether the new user's email domain already belongs to an existing account. If so, block registration and tell them to contact their administrator. If not, registration proceeds normally and creates a new account. Common email domains (gmail.com, yahoo.com, outlook.com, etc.) are excluded from this check so personal-email users can always register freely.

2. **Team invites** — the account owner can invite new users by email, assigning them a role. The invited user receives an email with a tokenised link to set their password and activate their account. This is the intended path for adding teammates when the domain guard blocks self-registration.

---

## Dependencies

- [x] `apps/accounts/` — `Account`, `AccountMembership` models exist
- [x] `apps/users/` — Custom `User` model with email-based auth, `RegistrationForm`, `RegisterUser` view
- [x] `apps/accounts/signals.py` — `post_save` signal creates `Account` + `AccountMembership` on new user registration
- [x] `TenantMiddleware` — attaches `request.account` from `AccountMembership`
- [ ] Email sending configured in Django settings (for invite emails)

---

## Implementation Checklist

### Phase 1 — Domain-Based Registration Guard

#### Common Domains List
- [x] Create a list of excluded common email domains (gmail.com, yahoo.com, outlook.com, hotmail.com, icloud.com, etc.) — store as a constant in `apps/accounts/constants.py` or directly in the form validation

#### Registration Form Validation
- [x] Add a `clean_email()` method to `RegistrationForm` in `apps/users/forms.py`:
  - Extract the domain from the email (`email.split('@')[1].lower()`)
  - If the domain is in the common domains list, skip the check and allow registration
  - Otherwise, check if any existing `Account` owner's email shares this domain (query `Account.objects.filter(owner__email__iendswith='@' + domain)`)
  - If a match exists, raise `ValidationError` with message: "An account already exists for this domain — contact your administrator to request access"
  - If no match, allow registration to proceed

#### Template
- [x] No template changes needed — the error will display through the existing form error rendering in `users/register.html`

---

### Phase 2 — Team Invites

#### Model
- [x] Add `AccountInvitation` model to `apps/accounts/models.py`:
  - `account` — ForeignKey to `Account`
  - `email` — EmailField (the invited user's email)
  - `role` — CharField with choices matching `AccountMembership.role` (start with `'member'` as default; `owner` should not be assignable via invite)
  - `token` — CharField(max_length=64) — a unique, URL-safe token for the invite link (generate via `secrets.token_urlsafe()`)
  - `invited_by` — ForeignKey to `User`
  - `accepted` — BooleanField(default=False)
  - `created_at` / `updated_at` — via `TenantAwareModel` base class
- [x] Run `makemigrations` and `migrate`

#### Invite Form
- [x] Create `InviteForm` in `apps/accounts/forms.py`:
  - Fields: `email`, `role`
  - `clean_email()` — check the user doesn't already exist as a member of this account; check no pending invite exists for this email on this account
  - Styled widgets via `__init__`

#### Invite View
- [x] Add `SendInviteView` in `apps/accounts/views.py` — `POST /account/invites/send/`:
  - Only account owner can send invites (check `request.user == request.account.owner`)
  - Creates `AccountInvitation` record with generated token
  - Sends invite email with a tokenised link to the accept URL
  - Redirects back to account settings (or a team management page)

#### Accept Invite View
- [x] Add `AcceptInviteView` in `apps/accounts/views.py` — `GET/POST /account/invites/accept/<str:token>/`:
  - Looks up `AccountInvitation` by token; returns 404 if not found or already accepted
  - `GET` — renders a registration-like form (password fields) pre-filled with the invited email
  - `POST` — creates the `User`, creates `AccountMembership` linking to the invitation's account with the assigned role, marks invitation as accepted, logs the user in, redirects to dashboard
  - **Important:** This view must NOT trigger the `post_save` signal's auto-account-creation — the invited user joins an existing account, not a new one

#### Signal Update
- [x] Update `create_account_for_new_user` in `apps/accounts/signals.py`:
  - Before creating a new account, check if an `AccountInvitation` with `email=instance.email` and `accepted=True` exists
  - If so, skip account creation (the `AcceptInviteView` already handled the membership)
  - If not, proceed with normal account creation

#### Email
- [x] Create an invite email template `templates/accounts/invite_email.html` (or plain text):
  - Include the account name, who invited them, and the accept link
  - Use Django's `send_mail()` or `EmailMessage`

#### URLs
- [x] `path('invites/send/', views.SendInviteView.as_view(), name='send_invite')`
- [x] `path('invites/accept/<str:token>/', views.accept_invite_view, name='accept_invite')`

#### Template — Accept Invite
- [x] Create `templates/accounts/accept_invite.html`:
  - Display the invited email (read-only)
  - Password and confirm password fields
  - Submit button to complete registration

#### Template — Team Management
- [x] Add a "Team Members" section to `templates/accounts/account_settings.html` (or a separate page):
  - List current members (from `AccountMembership`) with email and role
  - List pending invites (from `AccountInvitation` where `accepted=False`)
  - Invite form (email + role + Send button)
  - Only visible to account owner

---

## Key Design Decisions

- **Domain check happens in form validation, not the view:** Keeps the logic with the form where it's testable and reusable. The view doesn't need to change.
- **Common domains are excluded:** Users with gmail.com, yahoo.com, etc. can always self-register freely. The domain guard only applies to corporate/custom domains.
- **Signal skip for invited users:** The existing `post_save` signal auto-creates an account for every new user. Invited users must not get a second account — the signal needs to detect and skip this case.
- **Token-based invite, not magic link login:** The invite link leads to a password-setting form, not a direct login. This ensures the invited user sets their own credentials.
- **`AccountInvitation` is a new model, not reusing Django's password reset:** While the token flow is similar, the invite carries role and account information that doesn't fit into Django's built-in reset machinery.
- **Do not expose account owner identity:** The domain guard error message says "contact your administrator" — it does not reveal who the owner is or what the account is called.

---

## Notes

- The `AcceptInviteView` is the trickiest part — it creates a user, links them to the account, and must coordinate with the `post_save` signal to avoid double account creation. Consider having the view create the user and membership directly, then set a flag (e.g., an attribute on the user instance before save) that the signal checks.
- Email configuration (SMTP backend, `EMAIL_HOST`, etc.) must be set up in Django settings before invite emails will actually send. For local development, use `EMAIL_BACKEND = 'django.core.mail.backends.console.EmailBackend'` to print emails to the console.
- Invite tokens should have an expiration (e.g., 7 days). Check `created_at` age in `AcceptInviteView` and show an "expired" message if too old.
- The `AccountMembership.role` choices currently only have `('owner', 'Owner')`. You'll need to add at least `('member', 'Member')` before invites work. Full role expansion (admin, viewer) is a Phase 5 item — just add `member` for now.
