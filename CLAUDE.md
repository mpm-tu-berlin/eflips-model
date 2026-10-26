# CLAUDE.md

This file provides guidance to Claude Code (claude.ai/code) when working with code in this repository.

eflips-model: shared SQLAlchemy + Alembic data model for the eFLIPS tools. Other `eflips-*` packages depend on it. Spec: `schema.pdf`.

## Commands
- Tests: `poetry run pytest tests/test_schedule.py::TestRotation::test_name`. They need `DATABASE_URL` (sqlite or postgres with postgis + btree_gist) and, for sqlite, `SPATIALITE_LIBRARY_PATH`. They **drop all tables** in `DATABASE_URL`, so never point it at a DB with real data.
- black and `mypy --strict` run automatically through hooks (`.claude/settings.json`). poetry may be missing locally: the hooks then skip those checks and CI is the authority, so say what you could not verify.

## Rules
- Always use `eflips.model.create_engine`, never `sqlalchemy.create_engine` (it loads SpatiaLite).
- Every change has to work on both PostgreSQL and SQLite. CI tests both on Python 3.11–3.15.
- Never hand-edit `poetry.lock`. Ask before adding a runtime dependency.

## Versioning (every PR to main)
Bump the version in `pyproject.toml` **and** `doc/conf.py` (they must match and must be above the PyPI version):
- patch: no API or schema change
- minor: backwards-compatible API additions, or schema changes with a migration
- major: breaking API or schema changes

The Stop hook blocks if package code changed without a bump, or if the two versions differ.
