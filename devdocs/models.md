# Flint Models Reference

This document details every model, its fields, and relationships. Use this as your blueprint when building each app.

---

## Notation Guide

| Symbol | Meaning |
|--------|---------|
| `PK` | Primary Key (auto-generated BigAutoField) |
| `FK` | Foreign Key |
| `*` | Required field |
| `?` | Optional/nullable field |
| `unique` | Must be unique |
| `indexed` | Should have database index |

---

## App: `users`

### User

Custom user model with email-based authentication. No username field.

| Field | Type | Constraints | Notes |
|-------|------|-------------|-------|
| `id` | BigAutoField | PK | Auto-generated |
| `email` | EmailField | *, unique | Primary identifier for auth |
| `password` | CharField | * | Handled by AbstractBaseUser |
| `first_name` | CharField(100) | ? | Optional display name |
| `last_name` | CharField(100) | ? | Optional display name |
| `is_active` | BooleanField | default=True | Can user log in? |
| `is_staff` | BooleanField | default=False | Can access Django admin? |
| `is_superuser` | BooleanField | default=False | Has all permissions? |
| `created_at` | DateTimeField | auto_now_add | When user registered |
| `updated_at` | DateTimeField | auto_now | Last profile update |
| `last_login` | DateTimeField | ? | Handled by AbstractBaseUser |

**Relationships:**
- Has many `AccountMembership` (through accounts app)
- Belongs to many `Account` (via AccountMembership)

**Notes:**
- Extends `AbstractBaseUser` and `PermissionsMixin`
- `USERNAME_FIELD = 'email'`
- `REQUIRED_FIELDS = []`

---

## App: `core`

### TimeStampedModel (Abstract)

Base model that other models inherit from. Not a database table.

| Field | Type | Constraints | Notes |
|-------|------|-------------|-------|
| `created_at` | DateTimeField | auto_now_add | Set once on creation |
| `updated_at` | DateTimeField | auto_now | Updated on every save |

---

### TenantAwareModel (Abstract)

Extends TimeStampedModel. For models that belong to an account.

| Field | Type | Constraints | Notes |
|-------|------|-------------|-------|
| `account` | FK(Account) | *, on_delete=CASCADE | Tenant scope |
| `created_at` | DateTimeField | auto_now_add | Inherited |
| `updated_at` | DateTimeField | auto_now | Inherited |

---

## App: `accounts`

### Account

The tenant/organization. All data is scoped to an account.

| Field | Type | Constraints | Notes |
|-------|------|-------------|-------|
| `id` | BigAutoField | PK | |
| `name` | CharField(255) | * | Organization display name |
| `slug` | SlugField | *, unique, indexed | URL-safe identifier |
| `is_active` | BooleanField | default=True | Can members access? |
| `created_at` | DateTimeField | auto_now_add | |
| `updated_at` | DateTimeField | auto_now | |

**Relationships:**
- Has many `AccountMembership`
- Has many `User` (via AccountMembership)
- Has many `Source`
- Has many `Insight`

**Notes:**
- Generate slug from name on creation
- Consider adding: `plan`, `stripe_customer_id` for future billing

---

### AccountMembership

Links users to accounts with role-based access.

| Field | Type | Constraints | Notes |
|-------|------|-------------|-------|
| `id` | BigAutoField | PK | |
| `account` | FK(Account) | *, on_delete=CASCADE | |
| `user` | FK(User) | *, on_delete=CASCADE | |
| `role` | CharField(20) | *, choices | owner/admin/member/viewer |
| `is_default` | BooleanField | default=False | User's default account on login |
| `created_at` | DateTimeField | auto_now_add | When user joined |
| `updated_at` | DateTimeField | auto_now | |

**Constraints:**
- `unique_together = ['account', 'user']` (one membership per account per user)

**Role Choices:**
- `owner` - Full access, can delete account, manage billing
- `admin` - Can manage sources, members (but not delete account)
- `member` - Can view/edit data, generate insights
- `viewer` - Read-only access

**Notes:**
- For MVP: just use `owner` role and skip complex permissions

---

### AccountInvitation (Post-MVP)

Pending invitations to join an account.

| Field | Type | Constraints | Notes |
|-------|------|-------------|-------|
| `id` | BigAutoField | PK | |
| `account` | FK(Account) | *, on_delete=CASCADE | |
| `email` | EmailField | * | Invited email address |
| `role` | CharField(20) | *, choices | Role they'll have on accept |
| `invited_by` | FK(User) | *, on_delete=CASCADE | Who sent the invite |
| `token` | CharField(64) | *, unique | Secure invite token |
| `expires_at` | DateTimeField | * | When invite expires |
| `accepted_at` | DateTimeField | ? | When accepted (null if pending) |
| `created_at` | DateTimeField | auto_now_add | |

**Notes:**
- Skip for MVP - build when adding team features

---

## App: `sources`

### SourceType

Registry of supported connector types.

| Field | Type | Constraints | Notes |
|-------|------|-------------|-------|
| `id` | BigAutoField | PK | |
| `name` | CharField(100) | *, unique | e.g., "PostgreSQL", "HubSpot" |
| `slug` | SlugField | *, unique | e.g., "postgresql", "hubspot" |
| `connector_class` | CharField(255) | * | Python path to connector class |
| `icon` | CharField(100) | ? | Icon class or emoji |
| `category` | CharField(50) | *, choices | database/api/file/warehouse |
| `is_active` | BooleanField | default=True | Available for new connections? |
| `config_schema` | JSONField | ? | JSON schema for required config fields |
| `created_at` | DateTimeField | auto_now_add | |

**Category Choices:**
- `database` - PostgreSQL, MySQL, etc.
- `api` - HubSpot, Salesforce, etc.
- `file` - S3, Google Sheets, etc.
- `warehouse` - Snowflake, BigQuery, etc.

**Notes:**
- Seed this table with initial connector types
- `connector_class` example: `"apps.sources.connectors.postgresql.PostgreSQLConnector"`

---

### Source

A connected data source belonging to an account.

| Field | Type | Constraints | Notes |
|-------|------|-------------|-------|
| `id` | BigAutoField | PK | |
| `account` | FK(Account) | *, on_delete=CASCADE | Tenant scope |
| `source_type` | FK(SourceType) | *, on_delete=PROTECT | What kind of source |
| `name` | CharField(255) | * | User-given display name |
| `description` | TextField | ? | User notes about this source |
| `credentials_encrypted` | TextField | * | Fernet-encrypted JSON blob |
| `is_active` | BooleanField | default=True | Include in syncs? |
| `last_synced_at` | DateTimeField | ? | When metadata last refreshed |
| `last_sync_status` | CharField(20) | ?, choices | success/failed/running |
| `created_at` | DateTimeField | auto_now_add | |
| `updated_at` | DateTimeField | auto_now | |

**Relationships:**
- Belongs to `Account`
- Belongs to `SourceType`
- Has many `Schema`
- Has many `SourceSyncLog`
- Has many `Insight` (via InsightTarget)

**Sync Status Choices:**
- `pending` - Never synced
- `running` - Sync in progress
- `success` - Last sync succeeded
- `failed` - Last sync failed

**Notes:**
- `credentials_encrypted` contains connection details (host, port, user, password, etc.)
- Decrypt only when needed, never log decrypted values
- Consider adding: `sync_frequency`, `next_sync_at` for scheduled syncs

---

### SourceSyncLog

History of sync attempts for auditing and debugging.

| Field | Type | Constraints | Notes |
|-------|------|-------------|-------|
| `id` | BigAutoField | PK | |
| `source` | FK(Source) | *, on_delete=CASCADE | |
| `status` | CharField(20) | *, choices | success/failed |
| `started_at` | DateTimeField | * | When sync began |
| `completed_at` | DateTimeField | ? | When sync finished |
| `schemas_found` | IntegerField | default=0 | Count of schemas discovered |
| `tables_found` | IntegerField | default=0 | Count of tables discovered |
| `columns_found` | IntegerField | default=0 | Count of columns discovered |
| `error_message` | TextField | ? | Error details if failed |
| `created_at` | DateTimeField | auto_now_add | |

**Notes:**
- Create a new log entry for each sync attempt
- Useful for showing sync history in UI

---

## App: `catalog`

### Schema

A schema/namespace within a data source.

| Field | Type | Constraints | Notes |
|-------|------|-------------|-------|
| `id` | BigAutoField | PK | |
| `source` | FK(Source) | *, on_delete=CASCADE | |
| `name` | CharField(255) | * | Schema name (e.g., "public") |
| `description` | TextField | ? | User or LLM-generated description |
| `is_system` | BooleanField | default=False | System schema (pg_catalog, etc.)? |
| `created_at` | DateTimeField | auto_now_add | |
| `updated_at` | DateTimeField | auto_now | |

**Constraints:**
- `unique_together = ['source', 'name']`

**Relationships:**
- Belongs to `Source`
- Has many `Table`

**Notes:**
- For APIs without schemas, create a default schema named "default"

---

### Table

A table, view, or API entity. Stores metadata only, never actual data.

| Field | Type | Constraints | Notes |
|-------|------|-------------|-------|
| `id` | BigAutoField | PK | |
| `schema` | FK(Schema) | *, on_delete=CASCADE | |
| `name` | CharField(255) | * | Table/entity name |
| `table_type` | CharField(20) | *, choices | table/view/materialized_view/api_entity |
| `description` | TextField | ? | User or LLM-generated description |
| `comment` | TextField | ? | Original DB comment if present |
| `row_count` | BigIntegerField | ? | Approximate row count |
| `size_bytes` | BigIntegerField | ? | Table size on disk |
| `is_system` | BooleanField | default=False | System table? |
| `created_at` | DateTimeField | auto_now_add | |
| `updated_at` | DateTimeField | auto_now | |

**Constraints:**
- `unique_together = ['schema', 'name']`

**Relationships:**
- Belongs to `Schema`
- Has many `Column`
- Has many `TableStatistics`
- Has many `Insight` (via InsightTarget)

**Table Type Choices:**
- `table` - Regular table
- `view` - Database view
- `materialized_view` - Materialized view
- `api_entity` - API endpoint treated as table

---

### Column

Column metadata within a table.

| Field | Type | Constraints | Notes |
|-------|------|-------------|-------|
| `id` | BigAutoField | PK | |
| `table` | FK(Table) | *, on_delete=CASCADE | |
| `name` | CharField(255) | * | Column name |
| `ordinal_position` | IntegerField | * | Column order (1-indexed) |
| `data_type` | CharField(100) | * | e.g., "varchar(255)", "integer" |
| `is_nullable` | BooleanField | default=True | Allows NULL? |
| `is_primary_key` | BooleanField | default=False | Part of primary key? |
| `is_foreign_key` | BooleanField | default=False | Is a foreign key? |
| `foreign_key_table` | FK(Table) | ?, on_delete=SET_NULL | Referenced table |
| `foreign_key_column` | CharField(255) | ? | Referenced column name |
| `default_value` | TextField | ? | Default value expression |
| `comment` | TextField | ? | Original DB comment if present |
| `description` | TextField | ? | User or LLM-generated description |
| `created_at` | DateTimeField | auto_now_add | |
| `updated_at` | DateTimeField | auto_now | |

**Constraints:**
- `unique_together = ['table', 'name']`

**Relationships:**
- Belongs to `Table`
- Optionally references another `Table` (for foreign keys)
- Has many `Insight` (via InsightTarget)

**Notes:**
- `foreign_key_table` is self-referential FK to Table model
- For composite foreign keys, you may need a separate ForeignKeyConstraint model (defer for MVP)

---

### TableStatistics (Post-MVP)

Point-in-time statistics snapshots.

| Field | Type | Constraints | Notes |
|-------|------|-------------|-------|
| `id` | BigAutoField | PK | |
| `table` | FK(Table) | *, on_delete=CASCADE | |
| `captured_at` | DateTimeField | * | When stats were collected |
| `row_count` | BigIntegerField | ? | Exact or estimated row count |
| `size_bytes` | BigIntegerField | ? | Table size |
| `column_stats` | JSONField | ? | Per-column stats (nulls, distinct, etc.) |
| `created_at` | DateTimeField | auto_now_add | |

**Notes:**
- Skip for MVP - add when you need time-series stats
- `column_stats` structure example:
```json
{
  "user_id": {"null_count": 0, "distinct_count": 1500},
  "email": {"null_count": 12, "distinct_count": 1488}
}
```

---

## App: `insights`

### InsightPrompt

Versioned LLM prompts for generating insights.

| Field | Type | Constraints | Notes |
|-------|------|-------------|-------|
| `id` | BigAutoField | PK | |
| `name` | CharField(100) | *, unique | e.g., "table_description" |
| `description` | TextField | ? | What this prompt generates |
| `prompt_template` | TextField | * | The actual prompt with {placeholders} |
| `provider` | CharField(20) | *, choices | openai/anthropic |
| `model` | CharField(50) | * | e.g., "gpt-4", "claude-3-sonnet" |
| `version` | IntegerField | default=1 | Increment when prompt changes |
| `is_active` | BooleanField | default=True | Use this version? |
| `created_at` | DateTimeField | auto_now_add | |
| `updated_at` | DateTimeField | auto_now | |

**Provider Choices:**
- `openai`
- `anthropic`

**Notes:**
- Seed with initial prompts for table descriptions
- Template example: "Describe this database table based on its columns: {column_list}"

---

### Insight

An LLM-generated or manually created insight.

| Field | Type | Constraints | Notes |
|-------|------|-------------|-------|
| `id` | BigAutoField | PK | |
| `account` | FK(Account) | *, on_delete=CASCADE | Tenant scope |
| `insight_type` | CharField(50) | *, choices | description/usage/quality/relationship |
| `title` | CharField(255) | ? | Optional title/summary |
| `content` | TextField | * | The actual insight text |
| `content_format` | CharField(20) | default='markdown' | markdown/plain/html |
| `source_type` | CharField(20) | *, choices | llm/manual |
| `prompt` | FK(InsightPrompt) | ?, on_delete=SET_NULL | Which prompt generated this |
| `llm_model` | CharField(50) | ? | Model used if LLM-generated |
| `llm_tokens_used` | IntegerField | ? | Token count for cost tracking |
| `is_approved` | BooleanField | default=False | User verified accuracy? |
| `approved_by` | FK(User) | ?, on_delete=SET_NULL | Who approved |
| `approved_at` | DateTimeField | ? | When approved |
| `created_by` | FK(User) | ?, on_delete=SET_NULL | Who created (manual) or triggered (LLM) |
| `created_at` | DateTimeField | auto_now_add | |
| `updated_at` | DateTimeField | auto_now | |

**Insight Type Choices:**
- `description` - What this table/column is
- `usage` - How to use this data
- `quality` - Data quality observations
- `relationship` - How entities relate

**Source Type Choices:**
- `llm` - Generated by LLM
- `manual` - Written by user

**Relationships:**
- Belongs to `Account`
- Belongs to `InsightPrompt` (optional)
- Has many `InsightTarget`

---

### InsightTarget

Links an insight to its target (source, table, or column). Polymorphic association.

| Field | Type | Constraints | Notes |
|-------|------|-------------|-------|
| `id` | BigAutoField | PK | |
| `insight` | FK(Insight) | *, on_delete=CASCADE | |
| `target_type` | CharField(20) | *, choices | source/table/column |
| `source` | FK(Source) | ?, on_delete=CASCADE | If target_type='source' |
| `table` | FK(Table) | ?, on_delete=CASCADE | If target_type='table' |
| `column` | FK(Column) | ?, on_delete=CASCADE | If target_type='column' |
| `created_at` | DateTimeField | auto_now_add | |

**Target Type Choices:**
- `source` - Insight about a data source
- `table` - Insight about a table
- `column` - Insight about a column

**Notes:**
- Only one of source/table/column should be set, matching target_type
- Add validation in model's `clean()` method
- An insight can have multiple targets (cross-entity insights)

---

### InsightBuilder (Post-MVP)

User-created exploration sessions for cross-source insights.

| Field | Type | Constraints | Notes |
|-------|------|-------------|-------|
| `id` | BigAutoField | PK | |
| `account` | FK(Account) | *, on_delete=CASCADE | |
| `name` | CharField(255) | * | Session name |
| `description` | TextField | ? | What user is exploring |
| `context` | JSONField | * | Selected sources, tables, questions |
| `generated_insight` | FK(Insight) | ?, on_delete=SET_NULL | Final generated insight |
| `created_by` | FK(User) | *, on_delete=CASCADE | |
| `created_at` | DateTimeField | auto_now_add | |
| `updated_at` | DateTimeField | auto_now | |

**Notes:**
- Skip for MVP - this is Phase 3 feature
- `context` stores the user's exploration state

---

## Relationship Diagram

```
User
 │
 └──< AccountMembership >── Account
                              │
                              ├──< Source ──< Schema ──< Table ──< Column
                              │       │                    │          │
                              │       │                    │          │
                              │       └────────────────────┴──────────┘
                              │                    │
                              │              InsightTarget
                              │                    │
                              └──< Insight ────────┘
                                     │
                                     └── InsightPrompt
```

**Legend:**
- `──<` = has many
- `>──` = belongs to

---

## MVP Models Only

For MVP, implement only these models:

| App | Models |
|-----|--------|
| `users` | User |
| `core` | TimeStampedModel, TenantAwareModel (abstract only) |
| `accounts` | Account, AccountMembership |
| `sources` | SourceType, Source, SourceSyncLog |
| `catalog` | Schema, Table, Column |
| `insights` | InsightPrompt, Insight, InsightTarget |

**Defer for later:**
- AccountInvitation
- TableStatistics
- InsightBuilder

---

## Field Type Quick Reference

| Django Field | PostgreSQL Type | Use For |
|--------------|-----------------|---------|
| CharField(n) | varchar(n) | Short text with max length |
| TextField | text | Long text, no max |
| EmailField | varchar(254) | Email addresses |
| SlugField | varchar(50) | URL-safe identifiers |
| IntegerField | integer | Whole numbers |
| BigIntegerField | bigint | Large numbers (row counts) |
| BooleanField | boolean | True/false flags |
| DateTimeField | timestamp | Dates with times |
| JSONField | jsonb | Structured data |
| ForeignKey | integer + FK constraint | Relationships |