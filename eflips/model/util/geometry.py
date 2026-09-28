import logging
import math
import os
from pathlib import Path
from typing import Dict, Iterator, List, Optional, Sequence, Tuple, TypeVar

import geoalchemy2
import platformdirs
import requests
from kv_cache import KVStore  # type: ignore[import-untyped]
from typing_extensions import deprecated

from eflips.model import AssocRouteStation, Route, Station

logger = logging.getLogger(__name__)

cache_dir = Path(platformdirs.user_cache_dir("eflips", "de.tu-berlin", "1"))
cache_dir.mkdir(parents=True, exist_ok=True)
cache_file = cache_dir / Path("eflips_ingest_altitude_cache.db")
store = KVStore(str(cache_file.absolute()))

#: Timeout for a single-point request.
HTTP_TIMEOUT_SECONDS = 10
#: Timeout for a batch request. A 1000-point OpenElevation lookup on a small self-hosted
#: server can take considerably longer than a single point.
BATCH_HTTP_TIMEOUT_SECONDS = 60

#: The Google Elevation API accepts at most 512 locations per request and bills per request,
#: not per location. See https://developers.google.com/maps/documentation/elevation/requests-elevation
GOOGLE_MAX_LOCATIONS_PER_REQUEST = 512
#: OpenElevation documents no limit for the POST endpoint; this keeps request bodies and
#: response times reasonable.
OPENELEVATION_MAX_LOCATIONS_PER_REQUEST = 1000

#: The altitude returned for every point when ``ELEVATION_DUMMY_MODE=True``.
DUMMY_ALTITUDE = 9999.0

LatLon = Tuple[float, float]
T = TypeVar("T")


def _dummy_mode() -> bool:
    return os.environ.get("ELEVATION_DUMMY_MODE") == "True"


def _cache_key(latlon: LatLon) -> str:
    """The on-disk cache key: rounded to 4 decimal places (~11 m). The format is stable across versions."""
    return f"{round(latlon[0], 4)},{round(latlon[1], 4)}"


def _chunked(items: Sequence[T], size: int) -> Iterator[Sequence[T]]:
    for start in range(0, len(items), size):
        yield items[start : start + size]


def _validate_latlons(latlons: Sequence[LatLon]) -> None:
    for index, (lat, lon) in enumerate(latlons):
        if not (math.isfinite(lat) and math.isfinite(lon)):
            raise ValueError(f"Coordinate {index} is not finite: {(lat, lon)}")
        if not (-90.0 <= lat <= 90.0 and -180.0 <= lon <= 180.0):
            raise ValueError(f"Coordinate {index} is out of range: {(lat, lon)}")


def get_altitudes_openelevation(latlons: Sequence[LatLon]) -> List[Optional[float]]:
    """
    Look up altitudes for many coordinates from an OpenElevation server.

    Requires the ``OPENELEVATION_URL`` environment variable to be set. Points are sent in
    batches of :data:`OPENELEVATION_MAX_LOCATIONS_PER_REQUEST` via ``POST /api/v1/lookup``.

    :param latlons: ``(latitude, longitude)`` pairs
    :return: one altitude per input point, in input order. ``None`` marks a point for which
        the server had no data (it answers ``0`` or a value below -9000 in that case).
    :raises ValueError: if the URL is not configured or a response is malformed
    :raises requests.RequestException: on network failure
    """
    if not latlons:
        return []
    base_url = os.getenv("OPENELEVATION_URL")
    if not base_url:
        raise ValueError("OPENELEVATION_URL not set")

    altitudes: List[Optional[float]] = []
    for chunk in _chunked(latlons, OPENELEVATION_MAX_LOCATIONS_PER_REQUEST):
        body = {
            "locations": [{"latitude": lat, "longitude": lon} for lat, lon in chunk]
        }
        response = requests.post(
            f"{base_url}/api/v1/lookup", json=body, timeout=BATCH_HTTP_TIMEOUT_SECONDS
        )
        response.raise_for_status()
        results = response.json().get("results")
        if not isinstance(results, list) or len(results) != len(chunk):
            raise ValueError(
                f"OpenElevation returned {len(results) if isinstance(results, list) else 'no'} "
                f"results for {len(chunk)} locations"
            )
        for result in results:
            elevation = result.get("elevation") if isinstance(result, dict) else None
            if not isinstance(elevation, (int, float)) or isinstance(elevation, bool):
                altitudes.append(None)
            elif elevation == 0 or elevation < -9000:
                # 0 (which is bad, because it can actually exist) and < -9000 are sentinel
                # values for "no elevation found"
                altitudes.append(None)
            else:
                altitudes.append(float(elevation))
    return altitudes


def get_altitudes_google(latlons: Sequence[LatLon]) -> List[float]:
    """
    Look up altitudes for many coordinates from the Google Maps Elevation API.

    Requires the ``GOOGLE_MAPS_API_KEY`` environment variable to be set. Points are sent in
    batches of :data:`GOOGLE_MAX_LOCATIONS_PER_REQUEST`, which is what Google bills for.

    :param latlons: ``(latitude, longitude)`` pairs
    :return: one altitude per input point, in input order
    :raises ValueError: if the key is not configured, the API reports a non-OK status, or a
        response is malformed
    :raises requests.RequestException: on network failure
    """
    if not latlons:
        return []
    api_key = os.getenv("GOOGLE_MAPS_API_KEY")
    if not api_key:
        raise ValueError("GOOGLE_MAPS_API_KEY not set")

    altitudes: List[float] = []
    for chunk in _chunked(latlons, GOOGLE_MAX_LOCATIONS_PER_REQUEST):
        # URL length: the worst case location "-89.123456,-179.123456" is 22 characters plus
        # the percent-encoded "|" separator (3), so 512 locations are 12,800 characters. With
        # the endpoint and key that stays well below Google's 16,384 character limit. Six
        # decimals (~11 cm) are far finer than the 4-decimal cache key, so nothing is lost.
        locations = "|".join(f"{lat:.6f},{lon:.6f}" for lat, lon in chunk)
        response = requests.get(
            "https://maps.googleapis.com/maps/api/elevation/json",
            params={"locations": locations, "key": api_key},
            timeout=BATCH_HTTP_TIMEOUT_SECONDS,
        )
        response.raise_for_status()
        data = response.json()
        if data.get("status") != "OK":
            raise ValueError(
                f"Google Elevation API returned status {data.get('status')!r}: "
                f"{data.get('error_message', 'no elevation found')}"
            )
        results = data.get("results")
        if not isinstance(results, list) or len(results) != len(chunk):
            raise ValueError(
                f"Google Elevation API returned {len(results) if isinstance(results, list) else 'no'} "
                f"results for {len(chunk)} locations"
            )
        for result in results:
            elevation = result.get("elevation") if isinstance(result, dict) else None
            if not isinstance(elevation, (int, float)) or isinstance(elevation, bool):
                raise ValueError(
                    "Google Elevation API returned a non-numeric elevation"
                )
            altitudes.append(float(elevation))
    return altitudes


def get_altitudes(latlons: Sequence[LatLon]) -> List[float]:
    """
    Look up altitudes for many coordinates at once.

    Coordinates are de-duplicated (at the ~11 m resolution of the cache key) and served from
    the on-disk ``kv_cache`` where possible. The remaining points are sent to OpenElevation in
    one batch if ``OPENELEVATION_URL`` is set; points it cannot answer fall back to the Google
    Maps Elevation API, which is queried in batches of 512 (it bills per request). Set
    ``ELEVATION_DUMMY_MODE=True`` to return :data:`DUMMY_ALTITUDE` for every point instead.

    :param latlons: ``(latitude, longitude)`` pairs
    :return: one altitude per input point, in input order
    :raises ValueError: if a coordinate is invalid, the cache holds an unusable value, or no
        provider can answer
    :raises requests.RequestException: if the Google lookup fails on the network level
    """
    if not latlons:
        return []
    if _dummy_mode():
        return [DUMMY_ALTITUDE] * len(latlons)
    _validate_latlons(latlons)

    keys = [_cache_key(latlon) for latlon in latlons]
    representative: Dict[str, LatLon] = {}
    for key, latlon in zip(keys, latlons):
        representative.setdefault(key, latlon)

    resolved: Dict[str, float] = {}
    missing: List[str] = []
    for key in representative:
        cached = store.get(key, default=None)
        if isinstance(cached, (int, float)) and not isinstance(cached, bool):
            resolved[key] = float(cached)
        elif cached is None:
            missing.append(key)
        else:
            raise ValueError(f"Invalid cache value for key {key}: {cached}")
    n_cached = len(resolved)

    n_openelevation = 0
    if missing:
        try:
            openelevation = get_altitudes_openelevation(
                [representative[key] for key in missing]
            )
        except (ValueError, requests.RequestException) as e:
            logger.warning(
                "OpenElevation lookup for %d points failed (%s); falling back to Google",
                len(missing),
                e,
            )
            openelevation = [None] * len(missing)
        still_missing: List[str] = []
        for key, altitude in zip(missing, openelevation):
            if altitude is None:
                still_missing.append(key)
            else:
                resolved[key] = altitude
                store.set(key, altitude)
        n_openelevation = len(missing) - len(still_missing)
        missing = still_missing

    if missing:
        google = get_altitudes_google([representative[key] for key in missing])
        for key, altitude in zip(missing, google):
            resolved[key] = altitude
            store.set(key, altitude)

    logger.info(
        "Resolved %d altitudes (%d unique): %d cached, %d from OpenElevation, %d from Google",
        len(latlons),
        len(representative),
        n_cached,
        n_openelevation,
        len(missing),
    )
    return [resolved[key] for key in keys]


@deprecated(
    "get_altitude_openelevation() is deprecated and will be removed in eflips-model 12; "
    "use get_altitudes_openelevation() with a batch of coordinates instead."
)
def get_altitude_openelevation(latlon: LatLon) -> float:
    """
    Get altitude information for a single latitude and longitude from an OpenElevation server.

    .. deprecated:: 11.3.0
        Use :func:`get_altitudes_openelevation` with a batch of coordinates instead.
    """
    altitude = get_altitudes_openelevation([latlon])[0]
    if altitude is None:
        raise ValueError("No elevation found")
    return altitude


@deprecated(
    "get_altitude_google() is deprecated and will be removed in eflips-model 12; "
    "use get_altitudes_google() with a batch of coordinates instead."
)
def get_altitude_google(latlon: LatLon) -> float:
    """
    Get altitude information for a single latitude and longitude from the Google Maps Elevation API.

    .. deprecated:: 11.3.0
        Use :func:`get_altitudes_google` with a batch of coordinates instead. Google bills per
        request, and one request can carry 512 coordinates.
    """
    return get_altitudes_google([latlon])[0]


@deprecated(
    "get_altitude() is deprecated and will be removed in eflips-model 12; "
    "use get_altitudes() with a batch of coordinates instead."
)
def get_altitude(latlon: LatLon) -> float:
    """
    Get altitude information for a single latitude and longitude.

    .. deprecated:: 11.3.0
        Use :func:`get_altitudes` with a batch of coordinates instead. Calling this in a loop
        costs one billed Google request per point instead of one per 512 points.
    """
    return get_altitudes([latlon])[0]


def geometry_has_z() -> bool:
    """
    Check whether the geometry types of Station, Route and AssocRouteStation have Z coordinates.

    :return: True if they have Z coordinates, False otherwise
    """
    assert isinstance(AssocRouteStation.location.type, geoalchemy2.types.Geometry)
    assert isinstance(Station.geom.type, geoalchemy2.types.Geometry)
    assert isinstance(Route.geom.type, geoalchemy2.types.Geometry)
    if Station.geom.type.geometry_type == "POINTZ":
        assert (
            AssocRouteStation.location.type.geometry_type == "POINTZ"
        ), f"Inconsistent geometry types: {Station.geom.type.geometry_type } vs {AssocRouteStation.location.type.geometry_type }"
        assert (
            Route.geom.type.geometry_type == "LINESTRINGZ"
        ), f"Inconsistent geometry types: {Station.geom.type.geometry_type } vs {Route.geom.type.geometry_type }"
        has_z = True
    elif Station.geom.type.geometry_type == "POINT":
        assert (
            AssocRouteStation.location.type.geometry_type == "POINT"
        ), f"Inconsistent geometry types: {Station.geom.type.geometry_type } vs {AssocRouteStation.location.type.geometry_type }"
        assert (
            Route.geom.type.geometry_type == "LINESTRING"
        ), f"Inconsistent geometry types: {Station.geom.type.geometry_type } vs {Route.geom.type.geometry_type }"
        has_z = False
    else:
        raise ValueError("eflips.model.Station.geom has unsupported geometry type")
    return has_z
