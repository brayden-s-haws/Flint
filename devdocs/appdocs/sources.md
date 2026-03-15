# sources app - MVP Checklist

## Models

- [x] `SourceType` — registry of supported connectors (MVP: PostgreSQL only)
- [x] `Source` — a connected data source belonging to an account, stores encrypted credentials
- [x] `SourceSyncLog` — history of sync attempts with status and metrics

## Admin

- [x] Register `SourceType`, `Source`, `SourceSyncLog` in admin

## Connectors

- [x] `BaseConnector` — abstract connector interface (test_connection, discover_catalog)
- [x] `PostgreSQLConnector` — native connector for PostgreSQL metadata extraction
- [x] `ConnectorRegistry` — lookup connectors by source type
- [x] `get_table_metadata` — add to `BaseConnector` and `PostgreSQLConnector`; needed by the sync action to fetch per-table detail (step 5)

## Encryption

- [x] Fernet encryption utility for storing/retrieving database credentials

## Views

- [x] Source list view — show all sources for the current account
- [x] Source create view — form to add a new PostgreSQL source (host, port, dbname, user, password)
- [x] Source detail view — show source info, sync history, and connected schemas/tables
- [x] Wire source name link in `source_list.html` → `{% url 'sources:detail' source.pk %}` (placeholder `href=""` until detail URL exists)
- [ ] Test connection action — verify credentials work before saving
- [ ] Trigger sync action — manually kick off metadata sync

## Templates

- [x] `sources/source_list.html` — list of connected sources
- [x] `sources/source_form.html` — add/edit source form
- [x] `sources/source_detail.html` — source detail with sync history

## URLs

- [x] `/sources/` — list  ← `name='list'` required; `{% url 'sources:list' %}` is already referenced in `templates/core/dashboard.html` (empty-state CTA button) and will 404 until this URL exists
- [x] `/sources/add/` — create
- [x] `/sources/<id>/` — detail
- [ ] `/sources/<id>/test/` — test connection
- [ ] `/sources/<id>/sync/` — trigger sync

---

## Build Order

1. ~~**Encryption utility** — `apps/sources/encryption.py`. Small and self-contained; required before credentials can be safely stored or used by connectors.~~
2. ~~**List + Create views, form template, URLs** — build the CRUD layer so `/sources/` and `/sources/add/` work. No connectors needed yet; just save and load source records.~~
3. ~~**BaseConnector + PostgreSQLConnector + ConnectorRegistry** — `apps/sources/connectors/`. Build after the UI exists so you can test against real source records.~~
4. ~~**Detail view + template** — shows source info and sync history; build after connectors so sync data is meaningful.~~
5. **Wire test connection and sync actions** — tie the test and sync URL actions to the connector layer. Also implement `get_table_metadata` on `BaseConnector` and `PostgreSQLConnector` for use by the sync action.

Note to self:Make sure you merge this branch once done and start a new one for connectors.