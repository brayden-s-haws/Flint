# Testing Plan

Write tests after the MVP is functionally complete. Focus on the flows that would break silently — auth, form validation, redirects, and anything touching the database.

Use Django's `TestCase` and `Client` throughout. No external testing libraries needed for MVP.

---

## apps.users

**Registration**
- GET `/auth/register/` returns 200
- POST with valid data creates a user, logs them in, and redirects
- POST with mismatched passwords returns 200 with non-field error
- POST with duplicate email returns 200 with field error
- POST with missing fields returns 200 with field errors

**Login**
- GET `/auth/login/` returns 200
- POST with valid credentials returns 302 and sets session
- POST with bad password returns 200 with non-field error
- POST with unknown email returns 200 with non-field error
- POST with `next` parameter redirects to `next` after login

**Logout**
- POST `/auth/logout/` clears session and redirects

---

## apps.accounts

_(fill in once accounts views are built)_

---

## apps.sources

_(fill in once sources views are built)_

- Source creation with valid credentials
- Source creation with missing fields
- Connection test — success and failure cases
- Sync trigger

---

## apps.catalog

_(fill in once catalog views are built)_

- Schema/table/column list views return 200
- Views are scoped to the correct account (no cross-tenant leakage)

**TableStatistics**
- Sync creates a `TableStatistics` record linked to the correct `Table`
- PostgreSQL connector returns `column_stats` in the expected shape
- `TableStatistics` model defaults (null rates, row count) are set correctly when stats are missing or partial

---

## apps.insights

_(fill in once insights views are built)_

- Insight generation triggers LLM call (mock the LLM in tests)
- Insight list and detail views return 200

---

## Notes

- Use `Client.force_login()` to skip auth setup in tests that aren't testing auth itself
- Mock external calls (LLM APIs, database connectors) with `unittest.mock.patch`
- Test multi-tenancy boundaries: a user from account A should not see account B's data