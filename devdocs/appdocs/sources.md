# sources app - MVP Checklist

## Models

- [x] `SourceType` — registry of supported connectors (MVP: PostgreSQL only)
- [x] `Source` — a connected data source belonging to an account, stores encrypted credentials
- [x] `SourceSyncLog` — history of sync attempts with status and metrics

## Admin

- [x] Register `SourceType`, `Source`, `SourceSyncLog` in admin

## Connectors

- [ ] `BaseConnector` — abstract connector interface (test_connection, discover_catalog, get_table_metadata)
- [ ] `PostgreSQLConnector` — native connector for PostgreSQL metadata extraction
- [ ] `ConnectorRegistry` — lookup connectors by source type

## Encryption

- [ ] Fernet encryption utility for storing/retrieving database credentials

## Views

- [ ] Source list view — show all sources for the current account
- [ ] Source create view — form to add a new PostgreSQL source (host, port, dbname, user, password)
- [ ] Source detail view — show source info, sync history, and connected schemas/tables
- [ ] Test connection action — verify credentials work before saving
- [ ] Trigger sync action — manually kick off metadata sync

## Templates

- [ ] `sources/source_list.html` — list of connected sources
- [ ] `sources/source_form.html` — add/edit source form
- [ ] `sources/source_detail.html` — source detail with sync history

## URLs

- [ ] `/sources/` — list  ← `name='list'` required; `{% url 'sources:list' %}` is already referenced in `templates/core/dashboard.html` (empty-state CTA button) and will 404 until this URL exists
- [ ] `/sources/add/` — create
- [ ] `/sources/<id>/` — detail
- [ ] `/sources/<id>/test/` — test connection
- [ ] `/sources/<id>/sync/` — trigger sync