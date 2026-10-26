---
paths:
  - "eflips/model/*.py"
  - "eflips/model/util/**"
---
# Model code

- Almost every table carries a non-null `scenario_id`. A new table or relationship must also be handled in `Scenario.clone()` (`general.py`), `util/export.py` and `util/export_json.py`.
- New model classes are re-exported at the bottom of `eflips/model/__init__.py`, below `Base` (moving them up causes circular imports).
- Code must work on PostgreSQL/PostGIS and SQLite/SpatiaLite. Copy the existing variant pattern for column types, e.g. `postgresql.JSONB().with_variant(JSON, "sqlite")`, `DateTime(timezone=True).with_variant(TimeStampWithTz, "sqlite")` (needs tz-aware datetimes). Postgres-only DDL goes through `DDL(...).execute_if(dialect="postgresql")`.
- Hard invariants are `CheckConstraint`s. Soft ones are `before_insert`/`before_update` listeners that emit `ConsistencyWarning`.
- A schema change needs an Alembic migration (see `.claude/rules/migrations.md`) and at least a minor version bump.
