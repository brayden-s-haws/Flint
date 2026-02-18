# Post-MVP: Deferred Features

Concrete features that are out of scope for the MVP but will need to be built. Organized by app.

For speculative or longer-horizon ideas, see `devdocs/potential_features.md`.

---

## accounts

- **Account settings page** — allow the account owner to rename their account (`/account/settings/`)
- **Team invites** — invite other users to join an account (`AccountInvitation` model planned, see `devdocs/architecture.md`)
- **Multi-account switching** — users can belong to more than one account; UI to switch context
- **Role-based permissions** — expand beyond `owner` only; add `admin`, `member`, `viewer` roles to `AccountMembership`

---

## catalog

- **TableStatistics** — snapshot-based stats (row counts, column null rates, etc.); model planned but not built for MVP
- **Schema filter on table list** — filter table list by source or schema (UI enhancement)

---

## insights

- **InsightBuilder** — cross-source exploration sessions; model planned (`InsightBuilder`) but deferred
- **Cross-source insights** — insights that span multiple sources or tables
- **Batch insight generation** — generate descriptions for all tables in a source at once (requires Celery)
- **Insight approval/rating** — thumbs up/down workflow so users can accept or reject generated insights

---

## core / infrastructure

- **Celery + Redis** — background task queue for scheduled syncs and batch insight generation
- **REST API** — `apps/api/` layer for programmatic access (post-MVP app, skip for now)
- **Scheduled syncs** — run source syncs on a cron schedule rather than manual trigger only