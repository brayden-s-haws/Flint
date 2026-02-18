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
- [x] `LOGIN_REDIRECT_URL` — currently `'/'`, will 404 until home view exists
- [x] `LOGOUT_REDIRECT_URL` — currently `'/'`, will 404 until home view exists

## Deferred

- [ ] **Post-login/logout redirects** — `LOGIN_REDIRECT_URL` and `LOGOUT_REDIRECT_URL` are both set to `'/'`. Update both in `settings.py` once the home/dashboard view is built and wired to that route.
- [ ] **Post-registration redirect** — `RegisterUser.success_url` is also `'/'`. Update on the view in `apps/users/views.py` at the same time.