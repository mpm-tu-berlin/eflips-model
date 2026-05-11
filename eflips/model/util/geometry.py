import os
from pathlib import Path
from typing import Tuple

import geoalchemy2
import platformdirs
import requests
from kv_cache import KVStore  # type: ignore[import-untyped]

from eflips.model import AssocRouteStation, Route, Station

cache_dir = Path(platformdirs.user_cache_dir("eflips", "de.tu-berlin", "1"))
cache_file = cache_dir / Path("eflips_ingest_altitude_cache.db")
store = KVStore(str(cache_file.absolute()))


def get_altitude_openelevation(latlon: Tuple[float, float]) -> float:
    """
    Get altitude information for a given latitude and longitude from an OpenElevation server.

    Requires the ``OPENELEVATION_URL`` environment variable to be set.
    """
    if not os.getenv("OPENELEVATION_URL"):
        raise ValueError("OPENELEVATION_URL not set")
    url = f"{os.getenv('OPENELEVATION_URL')}/api/v1/lookup?locations={latlon[0]},{latlon[1]}"

    response = requests.get(url)
    response.raise_for_status()
    data = response.json()
    if "elevation" in data["results"][0]:
        assert isinstance(data["results"][0]["elevation"], float) or isinstance(
            data["results"][0]["elevation"], int
        )
        result = data["results"][0]["elevation"]
        # 0 (which is bad, because it can actually exist) and < -9000 are sentinel values for "no elevation found"
        if result == 0 or result < -9000:
            raise ValueError("No elevation found")
        return result
    else:
        raise ValueError("No elevation found")


def get_altitude_google(latlon: Tuple[float, float]) -> float:
    """
    Get altitude information for a given latitude and longitude from the Google Maps Elevation API.

    Requires the ``GOOGLE_MAPS_API_KEY`` environment variable to be set.
    """
    if not os.getenv("GOOGLE_MAPS_API_KEY"):
        raise ValueError("GOOGLE_MAPS_API_KEY not set")

    url = f"https://maps.googleapis.com/maps/api/elevation/json?locations={latlon[0]},{latlon[1]}&key={os.getenv('GOOGLE_MAPS_API_KEY')}"

    response = requests.get(url)
    response.raise_for_status()
    data = response.json()
    if data["status"] != "OK":
        raise ValueError("No elevation found")
    assert isinstance(data["results"][0]["elevation"], float) or isinstance(
        data["results"][0]["elevation"], int
    )

    altitude = data["results"][0]["elevation"]

    return altitude


def get_altitude(latlon: Tuple[float, float]) -> float:
    """
    Get altitude information for a given latitude and longitude.

    Tries OpenElevation first, then falls back to Google Maps. Results are cached
    on disk (rounded to 4 decimal places, ~11m resolution) via ``kv_cache``.
    Set ``ELEVATION_DUMMY_MODE=True`` to return a constant dummy altitude.
    """
    if "ELEVATION_DUMMY_MODE" in os.environ:
        if os.environ["ELEVATION_DUMMY_MODE"] == "True":
            return 9999.0

    rounded_lat = round(latlon[0], 4)
    rounded_lon = round(latlon[1], 4)
    cache_key = f"{rounded_lat},{rounded_lon}"
    result_or_none = store.get(cache_key, default=None)
    if isinstance(result_or_none, float) or isinstance(result_or_none, int):
        altitude = result_or_none
    elif result_or_none is None:
        try:
            altitude = get_altitude_openelevation(latlon)
        except ValueError:
            altitude = get_altitude_google(latlon)
        store.set(cache_key, altitude)
    else:
        raise ValueError(f"Invalid cache value for key {cache_key}: {result_or_none}")
    return altitude


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
