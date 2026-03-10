# catalog app - MVP Checklist

## Models

- [x] `Schema` — schema/namespace within a source
- [x] `Table` — table or view metadata (name, type, row count, belongs to schema)
- [x] `Column` — column metadata (name, data type, nullable, primary key, belongs to table)

## Admin

- [x] Register `Schema`, `Table`, `Column` in admin

## Views

- [ ] Table list view — browse all tables, filterable by source/schema
- [ ] Table detail view — show columns, metadata, and linked insights

## Templates

- [ ] `catalog/table_list.html` — browsable table list
- [ ] `catalog/table_detail.html` — table detail with column list and insights

## URLs

- [ ] `/catalog/` — table list (all sources)
- [ ] `/catalog/<id>/` — table detail

## MVP Notes

- TableStatistics model is deferred — no stats collection in MVP
- Metadata is populated by the sync action in the sources app, not manually entered

## Cross-App Integration (revisit when catalog app is built)

- `SourceDetailView` in `apps/sources/views.py` needs schema context added to `get_context_data` once catalog models are queryable. Pattern: `context['schemas'] = self.object.schema_set.prefetch_related('table_set')`
- `source_detail.html` needs its schema/tables section fleshed out (currently shows an empty state placeholder)