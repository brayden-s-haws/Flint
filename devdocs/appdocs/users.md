# users app - MVP Checklist

## Models

- [x] `User` — custom user model extending `AbstractUser`, email-based auth, no username

## Admin

- [x] Register `User` in admin with useful display fields (email, is_active, date_joined)

## Views

- [x] Registration view (`RegisterUser` in `apps/users/views.py`)
- [x] Login view (using Django's built-in `LoginView`, wired in urls.py)
- [x] Logout view (using Django's built-in `LogoutView`, wired in urls.py)

## Templates

- [x] `users/register.html` — signup form
- [x] `users/login.html` — login form

## URLs

- [x] `/auth/register/` — registration
- [x] `/auth/login/` — login
- [x] `/auth/logout/` — logout

## Settings

- [x] `AUTH_USER_MODEL = 'users.User'`
- [x] `LOGIN_URL = 'users:login'`
- [x] `LOGIN_REDIRECT_URL = 'core:dashboard'`
- [x] `LOGOUT_REDIRECT_URL = 'users:login'`

## Deferred

- [x] **Post-login/logout redirects** — updated to `core:dashboard` and `users:login` in `settings.py`
- [x] **Post-registration redirect** — `RegisterUser.success_url` updated to `reverse_lazy('core:dashboard')`