---
name: MVP Status
description: Flint MVP is complete as of 2026-03-30; active work is now post-MVP
type: project
---

MVP is complete as of 2026-03-30. All five core features are built and working:
1. User registration/login (email-based)
2. Connect PostgreSQL sources with encrypted credentials
3. Sync metadata (schemas, tables, columns)
4. Generate LLM table descriptions
5. Browse and view insights

**Why:** The MVP validated the core value proposition — generating useful metadata insights from PostgreSQL sources without storing actual data.

**How to apply:** Do not frame new work as "building the MVP." Current focus is post-MVP: UI polish (`devdocs/ui/cleanup.md`) and Phase 2 features (`devdocs/appdocs/post_mvp.md`). Active branch is `feature/ui-cleanup`.