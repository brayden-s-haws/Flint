# Logging Plan

Add logging after the MVP is functionally complete and tested. Focus on the flows that fail silently or involve external systems — auth, tenant resolution, credential encryption, sync operations, and LLM calls.

Use Python's standard `logging` module throughout. No external logging libraries needed for MVP. All loggers should use the `__name__` convention so the module hierarchy is preserved in log output.

---

## Settings Configuration

Add a `LOGGING` dict to `settings.py`. The structure below is the target state:

- **Console handler** for development (DEBUG and above)
- **File handler** for production (WARNING and above, rotating)
- **Django's request logger** to capture 4xx/5xx automatically
- **App-level loggers** for each Django app in `apps/`

Logger name pattern: `apps.<app_name>` (e.g., `apps.sources`, `apps.insights`)

Each module should declare its logger at the top, below imports:
```
logger = logging.getLogger(__name__)
```

Do not use the root logger directly. Always use named loggers.

---

## What NOT to Log

Never log the following, even at DEBUG level:

- Raw database passwords or connection strings
- Plaintext credentials before encryption
- Full Fernet ciphertext (it's reversible with the key)
- Session tokens or auth cookies
- LLM prompt contents that may contain user data
- Any field named `password`, `secret`, `token`, or `key`

Log presence/absence and shape, not values. For example: log `"credentials present: True"` not the credentials themselves.

---

## apps.accounts

**TenantMiddleware** (`apps/accounts/middleware.py`)

- INFO when middleware resolves `request.account` successfully — include account ID (not name)
- WARNING when an authenticated user has no AccountMembership — include user ID
- DEBUG when middleware skips unauthenticated requests (expected, high frequency — confirm DEBUG only)

---

## apps.users

**Registration**

- INFO on successful user creation — include user ID, account ID
- WARNING on failed registration attempt — include field-level error keys (not values)
- Do not log email addresses in any event

**Login / Logout**

- INFO on successful login — include user ID
- WARNING on failed login attempt — include failure reason (bad password vs. unknown user), never include the submitted password
- INFO on logout — include user ID

---

## apps.sources

**Encryption** (`apps/sources/encryption.py`)

- DEBUG when `_get_fernet()` initializes successfully
- ERROR when `ENCRYPTION_KEY` is missing or malformed (before raising `ImproperlyConfigured`)
- DEBUG on encrypt/decrypt entry and exit — log operation name and source ID only, never the payload
- ERROR when decryption fails — include source ID and exception type

**Source creation** (`apps/sources/views.py`)

- INFO on successful source creation — include source ID, source type, account ID
- WARNING on form validation failure — include field-level error keys
- ERROR if credential encryption raises during `form_valid()` — include exception type

**Source sync** (sync logic, when built)

- INFO when a sync job starts — include source ID, sync log ID
- INFO when a sync job completes — include source ID, sync log ID, `records_synced` count, duration in seconds
- ERROR when a sync job fails — include source ID, sync log ID, error message from `SourceSyncLog.error_message`
- WARNING when a sync is already running for a source (duplicate trigger guard)

---

## apps.catalog

**Metadata sync** (schema/table/column population, when built)

- DEBUG when schema discovery begins — include source ID, schema count discovered
- DEBUG when table discovery begins — include source ID, schema name, table count
- INFO when a full metadata sync completes — include source ID, totals (schemas, tables, columns)
- WARNING when a table or column is skipped due to unsupported type or parsing error — include source ID, object name, reason
- ERROR on connector-level failures — include source ID, exception type

---

## apps.insights

**LLM calls** (when built)

- INFO when an insight generation job starts — include insight ID, target type, provider name
- INFO when an LLM call completes — include insight ID, provider, model name, token usage if available
- WARNING when an LLM call is retried — include insight ID, attempt number, reason
- ERROR when an LLM call fails permanently — include insight ID, provider, exception type
- Never log prompt text or LLM response content at INFO or above

---

## Cross-Cutting Concerns

**Multi-tenancy boundary violations**

- WARNING (or ERROR) any time `TenantQuerysetMixin.get_queryset()` is called without `request.account` — this should never happen in normal flow
- WARNING if a queryset filter would have returned cross-tenant results before the account filter was applied (only if detectable)

**Unhandled exceptions**

- Django's default 500 handler logs tracebacks automatically — don't duplicate it
- For HTMX partial views that return error HTML instead of raising, log WARNING with the context that triggered the degraded response

**Startup checks**

- Log ENCRYPTION_KEY presence check at startup (not the key itself) — can be done in `AppConfig.ready()`

---

## Log Levels — Quick Reference

| Level | When to use |
|-------|-------------|
| DEBUG | High-frequency internal state, connector loops, ORM query counts |
| INFO | Business events with clear outcomes (user created, sync completed) |
| WARNING | Unexpected but recoverable states (missing account, LLM retry) |
| ERROR | Failures that require attention (encryption failure, sync crash) |
| CRITICAL | Reserved for catastrophic failures (data loss risk, total service outage) |

---

## Notes

- Use `extra={"source_id": ..., "account_id": ...}` on log calls to attach structured context — this makes filtering in log aggregators straightforward later
- Do not use f-strings for log messages — use `%s` style so the string isn't formatted if the log level is disabled
  - Correct: `logger.info("sync complete for source %s", source.id)`
  - Wrong: `logger.info(f"sync complete for source {source.id}")`
- For long-running jobs (sync, LLM calls), log both entry and exit so duration can be derived from timestamps
- When Django moves to production, wire the file handler to a log aggregator (Datadog, Papertrail, etc.) — the `LOGGING` config is already structured for that