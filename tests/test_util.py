import math
from typing import Any, Dict, List, Optional

import pytest
import requests

from eflips.model.util import (
    geometry_has_z,
    get_altitude,
    get_altitude_google,
    get_altitude_openelevation,
    get_altitudes,
    get_altitudes_google,
    get_altitudes_openelevation,
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


class _DictStore:
    def __init__(self, initial: Optional[Dict[str, Any]] = None):
        self.data: Dict[str, Any] = dict(initial or {})

    def get(self, key, default=None):
        return self.data.get(key, default)

    def set(self, key, value):
        self.data[key] = value


class _FakeResponse:
    def __init__(self, payload: Any, status_code: int = 200):
        self._payload = payload
        self.status_code = status_code

    def raise_for_status(self) -> None:
        if self.status_code >= 400:
            raise requests.HTTPError(f"status {self.status_code}")

    def json(self) -> Any:
        return self._payload


@pytest.fixture
def bypass_cache(monkeypatch):
    monkeypatch.setattr("eflips.model.util.geometry.store", _NullStore())


@pytest.fixture
def no_dummy_mode(monkeypatch):
    monkeypatch.delenv("ELEVATION_DUMMY_MODE", raising=False)


class TestGetAltitudes:
    def test_empty_input_makes_no_lookup(self, monkeypatch, no_dummy_mode):
        def explode(*args, **kwargs):  # pragma: no cover
            raise AssertionError("no lookup expected")

        monkeypatch.setattr("eflips.model.util.geometry.store", explode)
        monkeypatch.setattr(
            "eflips.model.util.geometry.get_altitudes_openelevation", explode
        )
        monkeypatch.setattr("eflips.model.util.geometry.get_altitudes_google", explode)
        assert get_altitudes([]) == []

    def test_dummy_mode(self, monkeypatch):
        monkeypatch.setenv("ELEVATION_DUMMY_MODE", "True")
        assert get_altitudes([(52.5, 13.4), (48.1, 11.6)]) == [9999.0, 9999.0]

    def test_order_preserved_and_duplicates_deduped(
        self, monkeypatch, bypass_cache, no_dummy_mode
    ):
        received: List[List[tuple]] = []

        def fake_open(latlons):
            received.append(list(latlons))
            return [float(index) for index in range(len(latlons))]

        def fake_google(latlons):  # pragma: no cover
            raise AssertionError("Google fallback should not have been called")

        monkeypatch.setattr(
            "eflips.model.util.geometry.get_altitudes_openelevation", fake_open
        )
        monkeypatch.setattr(
            "eflips.model.util.geometry.get_altitudes_google", fake_google
        )
        # The third point is within cache-key resolution of the first one.
        points = [(52.5, 13.4), (48.1, 11.6), (52.50001, 13.40001), (48.1, 11.6)]
        result = get_altitudes(points)
        assert received == [[(52.5, 13.4), (48.1, 11.6)]]
        assert result == [0.0, 1.0, 0.0, 1.0]

    def test_cache_hits_are_not_looked_up_and_misses_are_written(
        self, monkeypatch, no_dummy_mode
    ):
        store = _DictStore({"52.5,13.4": 100})
        monkeypatch.setattr("eflips.model.util.geometry.store", store)
        received: List[List[tuple]] = []

        def fake_open(latlons):
            received.append(list(latlons))
            return [7.5] * len(latlons)

        monkeypatch.setattr(
            "eflips.model.util.geometry.get_altitudes_openelevation", fake_open
        )
        result = get_altitudes([(52.5, 13.4), (48.1, 11.6)])
        assert result == [100.0, 7.5]
        assert received == [[(48.1, 11.6)]]
        assert store.data == {"52.5,13.4": 100, "48.1,11.6": 7.5}

    def test_partial_fallback_to_google(self, monkeypatch, bypass_cache, no_dummy_mode):
        google_received: List[List[tuple]] = []

        def fake_open(latlons):
            return [None, 5.0, None]

        def fake_google(latlons):
            google_received.append(list(latlons))
            return [11.0, 33.0]

        monkeypatch.setattr(
            "eflips.model.util.geometry.get_altitudes_openelevation", fake_open
        )
        monkeypatch.setattr(
            "eflips.model.util.geometry.get_altitudes_google", fake_google
        )
        points = [(1.0, 1.0), (2.0, 2.0), (3.0, 3.0)]
        assert get_altitudes(points) == [11.0, 5.0, 33.0]
        assert google_received == [[(1.0, 1.0), (3.0, 3.0)]]

    @pytest.mark.parametrize(
        "error",
        [requests.ConnectionError("down"), ValueError("OPENELEVATION_URL not set")],
    )
    def test_openelevation_failure_sends_everything_to_google(
        self, monkeypatch, bypass_cache, no_dummy_mode, error
    ):
        google_received: List[List[tuple]] = []

        def failing_open(latlons):
            raise error

        def fake_google(latlons):
            google_received.append(list(latlons))
            return [17.0] * len(latlons)

        monkeypatch.setattr(
            "eflips.model.util.geometry.get_altitudes_openelevation", failing_open
        )
        monkeypatch.setattr(
            "eflips.model.util.geometry.get_altitudes_google", fake_google
        )
        points = [(1.0, 1.0), (2.0, 2.0)]
        assert get_altitudes(points) == [17.0, 17.0]
        assert google_received == [points]

    def test_google_failure_propagates(self, monkeypatch, bypass_cache, no_dummy_mode):
        monkeypatch.setattr(
            "eflips.model.util.geometry.get_altitudes_openelevation",
            lambda latlons: [None] * len(latlons),
        )

        def failing_google(latlons):
            raise ValueError("Google Elevation API returned status 'REQUEST_DENIED'")

        monkeypatch.setattr(
            "eflips.model.util.geometry.get_altitudes_google", failing_google
        )
        with pytest.raises(ValueError, match="REQUEST_DENIED"):
            get_altitudes([(1.0, 1.0)])

    @pytest.mark.parametrize(
        "bad", [(math.nan, 13.4), (52.5, math.inf), (91.0, 0.0), (0.0, -181.0)]
    )
    def test_invalid_coordinates_are_rejected(self, bypass_cache, no_dummy_mode, bad):
        with pytest.raises(ValueError, match="Coordinate 1"):
            get_altitudes([(52.5, 13.4), bad])

    def test_invalid_cache_value_is_rejected(self, monkeypatch, no_dummy_mode):
        monkeypatch.setattr(
            "eflips.model.util.geometry.store", _DictStore({"52.5,13.4": "garbage"})
        )
        with pytest.raises(ValueError, match="Invalid cache value"):
            get_altitudes([(52.5, 13.4)])


class TestGetAltitudesGoogle:
    @pytest.fixture
    def api_key(self, monkeypatch):
        monkeypatch.setenv("GOOGLE_MAPS_API_KEY", "x" * 39)

    def test_chunks_at_512_and_keeps_order(self, monkeypatch, api_key):
        calls: List[Dict[str, Any]] = []

        def fake_get(url, params=None, timeout=None):
            calls.append({"url": url, "params": params, "timeout": timeout})
            locations = params["locations"].split("|")
            prepared = requests.Request("GET", url, params=params).prepare()
            assert prepared.url is not None and len(prepared.url) < 16384
            return _FakeResponse(
                {
                    "status": "OK",
                    "results": [
                        {"elevation": float(index), "location": {}}
                        for index in range(len(locations))
                    ],
                }
            )

        monkeypatch.setattr("eflips.model.util.geometry.requests.get", fake_get)
        # Worst-case-length coordinates to exercise the URL budget.
        points = [(-89.123456 + i * 1e-6, -179.123456) for i in range(1100)]
        result = get_altitudes_google(points)
        assert [len(c["params"]["locations"].split("|")) for c in calls] == [
            512,
            512,
            76,
        ]
        assert result == [float(i) for i in range(512)] + [
            float(i) for i in range(512)
        ] + [float(i) for i in range(76)]
        assert calls[0]["params"]["locations"].startswith("-89.123456,-179.123456|")
        assert all(c["params"]["key"] == "x" * 39 for c in calls)

    def test_non_ok_status_raises(self, monkeypatch, api_key):
        monkeypatch.setattr(
            "eflips.model.util.geometry.requests.get",
            lambda *a, **k: _FakeResponse(
                {"status": "REQUEST_DENIED", "error_message": "bad key", "results": []}
            ),
        )
        with pytest.raises(ValueError, match="REQUEST_DENIED.*bad key"):
            get_altitudes_google([(52.5, 13.4)])

    def test_result_count_mismatch_raises(self, monkeypatch, api_key):
        monkeypatch.setattr(
            "eflips.model.util.geometry.requests.get",
            lambda *a, **k: _FakeResponse(
                {"status": "OK", "results": [{"elevation": 1.0}]}
            ),
        )
        with pytest.raises(ValueError, match="1 results for 2 locations"):
            get_altitudes_google([(52.5, 13.4), (48.1, 11.6)])

    def test_raises_without_api_key_before_any_request(self, monkeypatch):
        monkeypatch.delenv("GOOGLE_MAPS_API_KEY", raising=False)

        def explode(*a, **k):  # pragma: no cover
            raise AssertionError("no request expected")

        monkeypatch.setattr("eflips.model.util.geometry.requests.get", explode)
        with pytest.raises(ValueError, match="GOOGLE_MAPS_API_KEY"):
            get_altitudes_google([(52.5, 13.4)])

    def test_empty_input(self, monkeypatch):
        monkeypatch.delenv("GOOGLE_MAPS_API_KEY", raising=False)
        assert get_altitudes_google([]) == []


class TestGetAltitudesOpenelevation:
    @pytest.fixture
    def url(self, monkeypatch):
        monkeypatch.setenv("OPENELEVATION_URL", "http://elevation.local")

    def test_posts_locations_and_maps_sentinels(self, monkeypatch, url):
        calls: List[Dict[str, Any]] = []

        def fake_post(url, json=None, timeout=None):
            calls.append({"url": url, "json": json, "timeout": timeout})
            return _FakeResponse(
                {
                    "results": [
                        {"latitude": 1.0, "longitude": 1.0, "elevation": 12.5},
                        {"latitude": 2.0, "longitude": 2.0, "elevation": 0},
                        {"latitude": 3.0, "longitude": 3.0, "elevation": -9999},
                        {"latitude": 4.0, "longitude": 4.0},
                    ]
                }
            )

        monkeypatch.setattr("eflips.model.util.geometry.requests.post", fake_post)
        points = [(1.0, 1.0), (2.0, 2.0), (3.0, 3.0), (4.0, 4.0)]
        assert get_altitudes_openelevation(points) == [12.5, None, None, None]
        assert calls[0]["url"] == "http://elevation.local/api/v1/lookup"
        assert calls[0]["json"] == {
            "locations": [{"latitude": lat, "longitude": lon} for lat, lon in points]
        }

    def test_chunks_at_1000(self, monkeypatch, url):
        sizes: List[int] = []

        def fake_post(url, json=None, timeout=None):
            sizes.append(len(json["locations"]))
            return _FakeResponse(
                {"results": [{"elevation": 1.0} for _ in json["locations"]]}
            )

        monkeypatch.setattr("eflips.model.util.geometry.requests.post", fake_post)
        result = get_altitudes_openelevation([(1.0, 1.0)] * 1001)
        assert sizes == [1000, 1]
        assert result == [1.0] * 1001

    def test_result_count_mismatch_raises(self, monkeypatch, url):
        monkeypatch.setattr(
            "eflips.model.util.geometry.requests.post",
            lambda *a, **k: _FakeResponse({"results": []}),
        )
        with pytest.raises(ValueError, match="0 results for 1 locations"):
            get_altitudes_openelevation([(52.5, 13.4)])

    def test_raises_without_env_var(self, monkeypatch):
        monkeypatch.delenv("OPENELEVATION_URL", raising=False)
        with pytest.raises(ValueError, match="OPENELEVATION_URL"):
            get_altitudes_openelevation([(52.5, 13.4)])


class TestDeprecatedSinglePointWrappers:
    def test_get_altitude_dummy_mode(self, monkeypatch):
        monkeypatch.setenv("ELEVATION_DUMMY_MODE", "True")
        with pytest.deprecated_call():
            assert get_altitude((52.5, 13.4)) == 9999.0

    def test_get_altitude_dispatches_to_batch(
        self, monkeypatch, bypass_cache, no_dummy_mode
    ):
        called = {}

        def fake_open(latlons):
            called["open"] = list(latlons)
            return [42.0]

        def fake_google(latlons):  # pragma: no cover
            raise AssertionError("Google fallback should not have been called")

        monkeypatch.setattr(
            "eflips.model.util.geometry.get_altitudes_openelevation", fake_open
        )
        monkeypatch.setattr(
            "eflips.model.util.geometry.get_altitudes_google", fake_google
        )
        with pytest.deprecated_call():
            assert get_altitude((-87.1234, 123.4567)) == 42.0
        assert called == {"open": [(-87.1234, 123.4567)]}

    def test_get_altitude_falls_back_to_google(
        self, monkeypatch, bypass_cache, no_dummy_mode
    ):
        monkeypatch.setattr(
            "eflips.model.util.geometry.get_altitudes_openelevation",
            lambda latlons: [None],
        )
        monkeypatch.setattr(
            "eflips.model.util.geometry.get_altitudes_google", lambda latlons: [17.0]
        )
        with pytest.deprecated_call():
            assert get_altitude((-87.2345, 123.5678)) == 17.0

    def test_get_altitude_openelevation_raises_on_unknown(self, monkeypatch):
        monkeypatch.setattr(
            "eflips.model.util.geometry.get_altitudes_openelevation",
            lambda latlons: [None],
        )
        with pytest.deprecated_call():
            with pytest.raises(ValueError, match="No elevation found"):
                get_altitude_openelevation((52.5, 13.4))

    def test_get_altitude_openelevation_raises_without_env_var(self, monkeypatch):
        monkeypatch.delenv("OPENELEVATION_URL", raising=False)
        with pytest.deprecated_call():
            with pytest.raises(ValueError):
                get_altitude_openelevation((52.5, 13.4))

    def test_get_altitude_google_returns_single_value(self, monkeypatch):
        monkeypatch.setattr(
            "eflips.model.util.geometry.get_altitudes_google", lambda latlons: [3.0]
        )
        with pytest.deprecated_call():
            assert get_altitude_google((52.5, 13.4)) == 3.0

    def test_get_altitude_google_raises_without_api_key(self, monkeypatch):
        monkeypatch.delenv("GOOGLE_MAPS_API_KEY", raising=False)
        with pytest.deprecated_call():
            with pytest.raises(ValueError):
                get_altitude_google((52.5, 13.4))
