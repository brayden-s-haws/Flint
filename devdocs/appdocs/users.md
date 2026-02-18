# users app - MVP Checklist

## Models

- [x] `User` — custom user model extending `AbstractUser`, email-based auth, no username

## Admin

- [x] Register `User` in admin with useful display fields (email, is_active, date_joined)

## Views

- [x] Registration view (signup with email + password)
- [ ] Login view (using Django's built-in `LoginView`)
- [ ] Logout view (using Django's built-in `LogoutView`)

## Templates

- [ ] `users/register.html` — signup form
- [ ] `users/login.html` — login form

## URLs

- [ ] `/auth/register/` — registration
- [ ] `/auth/login/` — login
- [ ] `/auth/logout/` — logout

## Settings

- [ ] `AUTH_USER_MODEL = 'users.User'`
- [ ] `LOGIN_URL`, `LOGIN_REDIRECT_URL`, `LOGOUT_REDIRECT_URL` configured
