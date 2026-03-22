# insights app - MVP Checklist

## Models

- [x] `Insight` — LLM-generated or manual insight content (text, type, status)
- [x] `InsightTarget` — links an insight to a specific table (polymorphic linking deferred, just table FK for MVP)
- [x] `InsightPrompt` — versioned LLM prompt templates stored in database

## Admin

- [x] Register `Insight`, `InsightTarget`, `InsightPrompt` in admin

## Services

- [x] LLM provider abstraction — base interface for generating insights
- [ ] OpenAI provider — call OpenAI API to generate table descriptions
- [ ] Anthropic provider — call Anthropic API to generate table descriptions
- [ ] Provider config — select which provider to use (settings or per-request)

## Views

- [ ] Generate insight action — trigger LLM description generation for a single table (sync call)
- [ ] Insight detail view — view a generated insight
- [ ] Insight list view — browse all insights for the account

## Templates

- [ ] `insights/insight_list.html` — list of generated insights
- [ ] `insights/insight_detail.html` — full insight view
- [ ] Inline insight display on `catalog/table_detail.html` (generate button + result)

## URLs

- [ ] `/insights/` — list
- [ ] `/insights/<id>/` — detail
- [ ] `/insights/generate/<table_id>/` — trigger generation for a table

## MVP Notes

- Sync LLM calls only (no Celery, no background tasks)
- One table at a time (no batch generation)
- InsightBuilder and cross-source insights are deferred