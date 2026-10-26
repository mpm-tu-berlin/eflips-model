---
paths:
  - "tests/**"
---
# Tests

- No conftest. `TestGeneral` in `tests/test_general.py` owns the `session` fixture (drop_all + `setup_database` on `DATABASE_URL`) and the `sample_content` scenario. Other test classes subclass it.
- Assert soft-validation failures with `pytest.warns(ConsistencyWarning)`.
- Do not hit real elevation APIs. Use `monkeypatch` / `ELEVATION_DUMMY_MODE=True`, as `tests/test_util.py` does.
