# catalog app - MVP Checklist

## Models

- [x] `Schema` — schema/namespace within a source
- [x] `Table` — table or view metadata (name, type, row count, belongs to schema)
- [x] `Column` — column metadata (name, data type, nullable, primary key, belongs to table)

## Admin

- [x] Register `Schema`, `Table`, `Column` in admin

## Views

- [x] Table list view — browse all tables, filterable by source/schema
- [x] Table detail view — show columns, metadata, and linked insights

## Templates

- [x] `catalog/table_list.html` — browsable table list
- [x] `catalog/table_detail.html` — table detail with column list and insights

## URLs

- [x] `/catalog/` — table list (all sources)
- [x] `/catalog/<id>/` — table detail

## MVP Notes

- TableStatistics model is deferred — no stats collection in MVP
- Metadata is populated by the sync action in the sources app, not manually entered

## Cross-App Integration COMPLETE

- [x] `SourceDetailView` — schema context added to `get_context_data`
- [x] `source_detail.html` — schemas/tables section fleshed out with linked table names

