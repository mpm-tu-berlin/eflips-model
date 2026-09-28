from eflips.model.util.geometry import (
    geometry_has_z,
    get_altitude,
    get_altitude_google,
    get_altitude_openelevation,
    get_altitudes,
    get_altitudes_google,
    get_altitudes_openelevation,
)

__all__ = [
    "geometry_has_z",
    "get_altitudes",
    "get_altitudes_google",
    "get_altitudes_openelevation",
    # Deprecated single-point variants, kept for backward compatibility until eflips-model 12.
    "get_altitude",
    "get_altitude_google",
    "get_altitude_openelevation",
]
