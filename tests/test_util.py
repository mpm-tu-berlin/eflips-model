import pytest

from eflips.model.util import (
    geometry_has_z,
    get_altitude,
    get_altitude_google,
    get_altitude_openelevation,
)


class TestGeometryHasZ:
    def test_returns_true_for_current_pointz_schema(self):
        # The model defines Station.geom and AssocRouteStation.location as POINTZ
        # and Route.geom as LINESTRINGZ, so the helper must report True.
        assert geometry_has_z() is True


class _NullStore:
    def get(self, key, default=None):
        return default

    def set(self, key, value):
        pass


@pytest.fixture
def bypass_cache(monkeypatch):
    monkeypatch.setattr("eflips.model.util.geometry.store", _NullStore())


class TestGetAltitude:
    def test_dummy_mode(self, monkeypatch):
        monkeypatch.setenv("ELEVATION_DUMMY_MODE", "True")
        assert get_altitude((52.5, 13.4)) == 9999.0

    def test_dispatches_to_openelevation_when_available(
        self, monkeypatch, bypass_cache
    ):
        called = {}

        def fake_open(latlon):
            called["open"] = latlon
            return 42.0

        def fake_google(latlon):  # pragma: no cover - should not be called
            called["google"] = latlon
            raise AssertionError("Google fallback should not have been called")

        monkeypatch.delenv("ELEVATION_DUMMY_MODE", raising=False)
        monkeypatch.setattr(
            "eflips.model.util.geometry.get_altitude_openelevation", fake_open
        )
        monkeypatch.setattr(
            "eflips.model.util.geometry.get_altitude_google", fake_google
        )
        result = get_altitude((-87.1234, 123.4567))
        assert result == 42.0
        assert called == {"open": (-87.1234, 123.4567)}

    def test_falls_back_to_google_when_openelevation_fails(
        self, monkeypatch, bypass_cache
    ):
        def failing_open(latlon):
            raise ValueError("simulated")

        def fake_google(latlon):
            return 17.0

        monkeypatch.delenv("ELEVATION_DUMMY_MODE", raising=False)
        monkeypatch.setattr(
            "eflips.model.util.geometry.get_altitude_openelevation", failing_open
        )
        monkeypatch.setattr(
            "eflips.model.util.geometry.get_altitude_google", fake_google
        )
        assert get_altitude((-87.2345, 123.5678)) == 17.0


class TestGetAltitudeOpenelevation:
    def test_raises_without_env_var(self, monkeypatch):
        monkeypatch.delenv("OPENELEVATION_URL", raising=False)
        with pytest.raises(ValueError):
            get_altitude_openelevation((52.5, 13.4))


class TestGetAltitudeGoogle:
    def test_raises_without_api_key(self, monkeypatch):
        monkeypatch.delenv("GOOGLE_MAPS_API_KEY", raising=False)
        with pytest.raises(ValueError):
            get_altitude_google((52.5, 13.4))
