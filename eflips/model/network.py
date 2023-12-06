from enum import auto, Enum as PyEnum
from typing import Any, List, TYPE_CHECKING

from geoalchemy2 import Geometry
from sqlalchemy import (
    BigInteger,
    Boolean,
    CheckConstraint,
    Enum as SqlEnum,
    event,
    Float,
    ForeignKey,
    Integer,
    Text,
)
from sqlalchemy.orm import Mapped, mapped_column, relationship

from eflips.model import Base

if TYPE_CHECKING:
    from eflips.model import Scenario, Trip, StopTime, Event


class Line(Base):
    """
    The Line represents a bus line, which is a collection of :class:`Route` that belong together. This may not
    include all routes that a bus on this line takes over its service day, since depot and deadhead routes are not
    included (they can be shared between multiple lines).
    """

    __tablename__ = "Line"

    id: Mapped[int] = mapped_column(BigInteger, primary_key=True)
    """The unique identifier of the battery type. Auto-incremented."""

    scenario_id: Mapped[int] = mapped_column(ForeignKey("Scenario.id"), nullable=False)
    """The unique identifier of the scenario. Foreign key to :attr:`Scenario.id`."""
    scenario: Mapped["Scenario"] = relationship("Scenario", back_populates="lines")
    """The scenario."""

    name: Mapped[str] = mapped_column(Text, nullable=False)
    """
    The name of the line. Usually a number or letter, e.g. "1" or "A" followed by the terminal stations.
    Example: "1 - Hauptbahnhof <-> Hauptfriedhof"
    """

    name_short: Mapped[str] = mapped_column(Text, nullable=True)
    """The short name of the line. Usually a number or letter, e.g. "1" or "A"."""

    routes: Mapped[list["Route"]] = relationship("Route", back_populates="line")


class Route(Base):
    """
    A route is a fixed geometry that a bus takes. It is a part of a :class:`Line`. A trip takes place on a route.
    """

    __tablename__ = "Route"

    id: Mapped[int] = mapped_column(BigInteger, primary_key=True)
    """The unique identifier of the battery type. Auto-incremented."""

    scenario_id: Mapped[int] = mapped_column(ForeignKey("Scenario.id"), nullable=False)
    """The unique identifier of the scenario. Foreign key to :attr:`Scenario.id`."""
    scenario: Mapped["Scenario"] = relationship("Scenario", back_populates="routes")
    """The scenario."""

    departure_station_id: Mapped[int] = mapped_column(
        ForeignKey("Station.id"), nullable=False
    )
    """The unique identifier of the departure station. Foreign key to :attr:`Station.id`."""
    departure_station: Mapped["Station"] = relationship(
        "Station",
        back_populates="routes_departing",
        foreign_keys=[departure_station_id],
    )
    """The departure station."""

    arrival_station_id: Mapped[int] = mapped_column(
        ForeignKey("Station.id"), nullable=False
    )
    """The unique identifier of the arrival station. Foreign key to :attr:`Station.id`."""
    arrival_station: Mapped["Station"] = relationship(
        "Station", back_populates="routes_arriving", foreign_keys=[arrival_station_id]
    )
    """The arrival station."""

    line_id: Mapped[int] = mapped_column(ForeignKey("Line.id"), nullable=True)
    """The unique identifier of the line. Foreign key to :attr:`Line.id`. May be ``None``."""
    line: Mapped[Line] = relationship("Line", back_populates="routes")
    """The line."""

    name: Mapped[str] = mapped_column(Text, nullable=False)
    """The name of the route. Usually a number followed by the terminal station. Example: "1 Hauptbahnhof -> Hauptfriedhof""" ""

    name_short: Mapped[str] = mapped_column(Text, nullable=True)
    """The short name of the route (if available)."""

    headsign: Mapped[str] = mapped_column(Text, nullable=True)
    """The headsign of the route (if available). This is whatever is displayed on the bus."""

    distance: Mapped[float] = mapped_column(Float, nullable=False)
    """The length of the route in meters."""

    geom: Mapped[Geometry] = mapped_column(
        Geometry("LINESTRINGZ", srid=4326), nullable=True
    )
    """
    The shape of the route as a polyline. If set, the length of this shape must be equal to :attr:`Route.distance`.
    Use WGS84 coordinates (EPSG:4326).
    """

    trips: Mapped[List["Trip"]] = relationship("Trip", back_populates="route")
    """The trips."""

    assoc_route_stations: Mapped[List["AssocRouteStation"]] = relationship(
        "AssocRouteStation", back_populates="route"
    )
    """The associated route stations. This contains metadata about the stops on the route, such as the partial distance."""

    stations: Mapped[List["Station"]] = relationship(
        "Station",
        secondary="AssocRouteStation",
        back_populates="routes",
        order_by="AssocRouteStation.elapsed_distance",
        viewonly=True,
    )
    """This is a list of all stations on the route."""

    __table_args__ = (
        CheckConstraint("distance > 0", name="route_distance_positive_check"),
        CheckConstraint(
            "geom IS NULL OR ST_Length(geom, True) = distance",
            name="route_shape_distance_check",
        ),
    )


@event.listens_for(Route, "before_insert")
@event.listens_for(Route, "before_update")
def check_route_before_insert_or_update(_: Any, __: Any, target: Route) -> None:
    """
    Check the route before flushing it to the database.
    - Ensure that the distance of the first stop time is 0
    - Ensure that the distance of the last stop time is the distance of the route
    - Ensure that the first and last associated route stations correspond to the departure and arrival stations

    - If we have stop times, we must ensure that the temporal order of stop times
      matches the spatial order of the stations.

    :param target:
    :return: Nothing. Raises an exception if the route is invalid.
    """
    if len(target.assoc_route_stations) > 0:
        sorted_assoc_route_stations = sorted(
            target.assoc_route_stations, key=lambda x: x.elapsed_distance
        )

        if sorted_assoc_route_stations[0].elapsed_distance != 0:
            raise ValueError(
                "The distance of the first stop time of a route must be 0."
            )

        if sorted_assoc_route_stations[-1].elapsed_distance != target.distance:
            raise ValueError(
                "The distance of the last stop time of a route must be the distance of the route."
            )

        if sorted_assoc_route_stations[0].station != target.departure_station:
            raise ValueError(
                "The first associated route station must correspond to the departure station."
            )

        if sorted_assoc_route_stations[-1].station != target.arrival_station:
            raise ValueError(
                "The last associated route station must correspond to the arrival station."
            )

        # Check that the order of the stop times matches the order of the stations
        for trip in target.trips:
            if len(trip.stop_times) > 0:
                sorted_stop_times = sorted(
                    trip.stop_times, key=lambda x: x.arrival_time
                )
                assoc_route_stations_copy = sorted_assoc_route_stations.copy()
                try:
                    while len(sorted_stop_times) > 0:
                        # Get the next associated route station
                        assoc_route_station = assoc_route_stations_copy.pop(0)

                        # Get the next stop time
                        stop_time = sorted_stop_times.pop(0)

                        # There may be associated route stations without stop times
                        while stop_time.station != assoc_route_station.station:
                            assoc_route_station = assoc_route_stations_copy.pop(0)
                except IndexError as e:
                    raise ValueError(
                        "The order of the stop times does not match the order of the stations."
                    ) from e


class VoltageLevel(PyEnum):
    """
    The voltage level of a charging infrastructure. Used in analysis and simulation to determine grid load.
    """

    HV = auto()
    """High Voltage, e.g. 110kV transmission grid"""

    HV_MV = auto()
    """Both high and medium voltage"""

    MV = auto()
    """Medium Voltage, e.g. 10kV distribution grid"""

    MV_LV = auto()
    """Both medium and low voltage"""

    LV = auto()
    """Low voltage, e.g. 400V three- phase"""


class ChargeType(PyEnum):
    """
    The type of charging infrastructure. Only vehicle types with opportunity charging can charge at opportunity
    charging stations.
    """

    depb = auto()
    """Only charge when vehicle is not on a rotation"""

    oppb = auto()
    """Aka „terminus charging“. While on a rotation, charge in the breaks between trips"""

    DEPOT = depb
    """Legacy value for depb"""

    OPPORTUNITY = oppb
    """Legacy value for oppb"""


class Station(Base):
    """
    A Station is a point on the map that a bus can stop at. It is visited on a :class:`Trip`.
    The station may not mark the exact location of the stop, but rather a point nearby, in case the station is part of a
    larger complex.
    """

    __tablename__ = "Station"

    id: Mapped[int] = mapped_column(BigInteger, primary_key=True)
    """The unique identifier of the battery type. Auto-incremented."""

    scenario_id: Mapped[int] = mapped_column(ForeignKey("Scenario.id"), nullable=False)
    """The unique identifier of the scenario. Foreign key to :attr:`Scenario.id`."""
    scenario: Mapped["Scenario"] = relationship("Scenario", back_populates="stations")
    """The scenario."""

    name: Mapped[str] = mapped_column(Text, nullable=False)
    """The name of the station. Example: "Hauptbahnhof" """
    name_short: Mapped[str] = mapped_column(Text, nullable=True)
    """The short name of the station (if available)."""

    geom: Mapped[Geometry] = mapped_column(
        Geometry("POINTZ", srid=4326), nullable=False
    )
    """The location of the station as a point. Use WGS84 coordinates (EPSG:4326)."""

    is_electrified = mapped_column(Boolean, nullable=False)
    """
    Whether the station has a charging infrastructure. If yes, then
    
    - `amount_charging_places` must be set
    - `power_per_charger` must be set
    - `power_total` must be set
    - `charge_type` must be set
    - `voltage_level` must be set
    """

    amount_charging_places = mapped_column(Integer, nullable=True)
    """
    The amount of charging poles at the station. If `is_electrified` is true, this must be set.
    """

    power_per_charger = mapped_column(Float, nullable=True)
    """
    The power per charger in kW. If `is_electrified` is true, this must be set.
    """

    power_total = mapped_column(Float, nullable=True)
    """
    The total power of the charging infrastructure in kW. If `is_electrified` is true, this must be set.
    """

    charge_type = mapped_column(SqlEnum(ChargeType), nullable=True)
    """
    The type of charging infrastructure. If `is_electrified` is true, this must be set. 
    
    When running simBA and eflips, this is set to `oppb` for all stations. `depb` only makes sense in standalone
    simBA runs.
    """

    voltage_level = mapped_column(SqlEnum(VoltageLevel), nullable=True)
    """
    The voltage level of the charging infrastructure. If `is_electrified` is true, this must be set.
    """

    routes_departing: Mapped[List["Route"]] = relationship(
        "Route",
        back_populates="departure_station",
        foreign_keys="Route.departure_station_id",
    )
    routes_arriving: Mapped[List["Route"]] = relationship(
        "Route",
        back_populates="arrival_station",
        foreign_keys="Route.arrival_station_id",
    )

    stop_times: Mapped[List["StopTime"]] = relationship(
        "StopTime", back_populates="station", order_by="StopTime.arrival_time"
    )
    """The stop times."""

    trips: Mapped[List["Trip"]] = relationship(
        "Trip", secondary="StopTime", back_populates="stations", viewonly=True
    )
    """The trips stopping at this station."""

    assoc_route_stations: Mapped[List["AssocRouteStation"]] = relationship(
        "AssocRouteStation", back_populates="station"
    )
    """The associated route stations. This contains metadata about the stops on the route, such as the partial distance."""

    routes: Mapped[List["Route"]] = relationship(
        "Route",
        secondary="AssocRouteStation",
        back_populates="stations",
        viewonly=True,
    )
    """This is a list of all routes that stop at this station."""

    events: Mapped[List["Event"]] = relationship("Event", back_populates="station")
    """The events that take place at this station. Only expected to be filled for charging at electrified stations."""

    # Create a check constraint to ensure that the charging infrastructure is only set if the station is electrified.
    __table_args__ = (
        CheckConstraint(
            "is_electrified=TRUE AND (amount_charging_places "
            "IS NOT NULL AND power_per_charger IS NOT NULL "
            "AND power_total IS NOT NULL "
            "AND charge_type IS NOT NULL "
            "AND voltage_level IS NOT NULL) OR "
            "is_electrified=FALSE AND (amount_charging_places "
            "IS NULL AND power_per_charger IS NULL "
            "AND power_total IS NULL "
            "AND charge_type IS NULL "
            "AND voltage_level IS NULL)",
            name="station_electrified_check",
        ),
    )


class AssocRouteStation(Base):
    """
    An association table between :class:`Route` and :class:`Station`. It is used to represent the stops on a route.
    """

    __tablename__ = "AssocRouteStation"

    id: Mapped[int] = mapped_column(BigInteger, primary_key=True)
    """The unique identifier of the association. Auto-incremented."""

    scenario_id: Mapped[int] = mapped_column(ForeignKey("Scenario.id"), nullable=False)
    """The unique identifier of the scenario. Foreign key to :attr:`Scenario.id`."""
    scenario: Mapped["Scenario"] = relationship(
        "Scenario", back_populates="assoc_route_stations"
    )
    """The scenario."""

    route_id: Mapped[int] = mapped_column(ForeignKey("Route.id"), nullable=False)
    """The unique identifier of the route. Foreign key to :attr:`Route.id`."""
    route: Mapped[Route] = relationship("Route", back_populates="assoc_route_stations")
    """The route."""

    station_id: Mapped[int] = mapped_column(ForeignKey("Station.id"), nullable=False)
    """The unique identifier of the station. Foreign key to :attr:`Station.id`."""
    station: Mapped[Station] = relationship(
        "Station", back_populates="assoc_route_stations"
    )
    """The station."""

    location: Mapped[Geometry] = mapped_column(
        Geometry("POINTZ", srid=4326), nullable=True
    )
    """An optional precise location of the this route's stop at the station. Use WGS84 coordinates (EPSG:4326)."""

    elapsed_distance: Mapped[float] = mapped_column(Float, nullable=False)
    """The distance in m that the bus has traveled when it reached this stop."""
