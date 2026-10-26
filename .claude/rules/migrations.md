---
paths:
  - "eflips/model/migrations/**"
---
# Alembic migrations

- Generate from `eflips/model/` with `DATABASE_URL` pointing at a DB at the current head: `alembic revision --autogenerate -m "vX.Y.Z"`. The message is the new package version. Review the output, because autogenerate misses things such as PostGIS details and enums.
- Released migrations are never edited. Add a new one instead.
- Migrations target PostgreSQL only (raw SQL and `postgresql.*` types are fine). SQLite databases are created fresh with `setup_database()`, which runs `create_all` and stamps head, so they never run migrations.
- Hand-written revision IDs are fine, but `down_revision` must point at the current single head.
