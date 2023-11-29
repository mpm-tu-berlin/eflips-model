from datetime import datetime, timedelta
from enum import auto, Enum as PyEnum
from typing import List, TYPE_CHECKING

from geoalchemy2 import Geometry
from sqlalchemy import (
    BigInteger,
    Boolean,
    CheckConstraint,
    DateTime,
    Enum as SqlEnum,
    Float,
    ForeignKey,
    Interval,
    Text,
)
from sqlalchemy.orm import Mapped, mapped_column, relationship

from eflips.model import Base

if TYPE_CHECKING:
    from eflips.model import Scenario


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

    shape: Mapped[Geometry] = mapped_column(
        Geometry("LINESTRING", srid=4326), nullable=True
    )
    """
    The shape of the route as a polyline. If set, the length of this shape must be equal to :attr:`Route.distance`.
    Use WGS84 coordinates (EPSG:4326).
    """

    trips: Mapped[List["Trip"]] = relationship("Trip", back_populates="route")


class VoltageLevel(PyEnum):
    """
    The voltage level of a charging infrastructure. Used in analysis and simulation to determine grid load.
    """

    LV = auto()
    """Low voltage, e.g. 400V three- phase"""

    MV = auto()
    """Medium Voltage, e.g. 10kV distribution grid"""


class ChargeType(PyEnum):
    """
    The type of charging infrastructure. Only vehicle types with opportunity charging can charge at opportunity
    charging stations.
    """

    DEPOT = auto()
    """Only charge when vehicle is not on a rotation"""

    OPPORTUNITY = auto()
    """Aka „terminus charging“. While on a rotation, charge in the breaks between trips"""


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

    location: Mapped[Geometry] = mapped_column(
        Geometry("POINT", srid=4326), nullable=False
    )
    """The location of the station as a point. Use WGS84 coordinates (EPSG:4326)."""

    is_electrified = mapped_column(Boolean, nullable=False)
    """
    Whether the station has a charging infrastructure. If yes, then
    
    - `amount_charging_poles` must be set
    - `power_per_charger` must be set
    - `power_total` must be set
    - `charge_type` must be set
    - `voltage_level` must be set
    """

    amount_charging_poles = mapped_column(BigInteger, nullable=True)
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
    
    When running simBA and eflips, this is set to `OPPORTUNITY` for all stations. `DEPOT` only makes sense in standalone
    simBA runs.
    """

    voltage_level = mapped_column(SqlEnum(VoltageLevel), nullable=True)
    """
    The voltage level of the charging infrastructure. If `is_electrified` is true, this must be set.
    """

    stop_times: Mapped[List["StopTime"]] = relationship(
        "StopTime", back_populates="station"
    )

    trips_departing: Mapped[List["Trip"]] = relationship(
        "Trip",
        back_populates="departure_station",
        foreign_keys="Trip.departure_station_id",
    )
    trips_arriving: Mapped[List["Trip"]] = relationship(
        "Trip", back_populates="arrival_station", foreign_keys="Trip.arrival_station_id"
    )

    # Create a check constraint to ensure that the charging infrastructure is only set if the station is electrified.
    __table_args__ = (
        CheckConstraint(
            "is_electrified=TRUE AND (amount_charging_poles "
            "IS NOT NULL AND power_per_charger IS NOT NULL "
            "AND power_total IS NOT NULL "
            "AND charge_type IS NOT NULL "
            "AND voltage_level IS NOT NULL) OR "
            "is_electrified=FALSE AND (amount_charging_poles "
            "IS NULL AND power_per_charger IS NULL "
            "AND power_total IS NULL "
            "AND charge_type IS NULL "
            "AND voltage_level IS NULL)",
            name="station_electrified_check",
        ),
    )


class TripType(PyEnum):
    """
    The type of a trip. Used in analysis to determine schedule efficiency.
    """

    EMPTY = auto()
    """= deadheading, vehicle if repositioning itself for passenger trip"""
    PASSENGER = auto()
    """Passengers may board"""


class Trip(Base):
    """
    A trip is a single run of a bus on a :class:`Route`. It is part of a :class:`Rotation`.
    """

    __tablename__ = "Trip"

    id: Mapped[int] = mapped_column(BigInteger, primary_key=True)
    """The unique identifier of the battery type. Auto-incremented."""

    scenario_id: Mapped[int] = mapped_column(ForeignKey("Scenario.id"), nullable=False)
    """The unique identifier of the scenario. Foreign key to :attr:`Scenario.id`."""
    scenario: Mapped["Scenario"] = relationship("Scenario", back_populates="trips")
    """The scenario."""

    route_id: Mapped[int] = mapped_column(ForeignKey("Route.id"), nullable=False)
    """The unique identifier of the route. Foreign key to :attr:`Route.id`."""
    route: Mapped[Route] = relationship("Route", back_populates="trips")
    """The route."""

    # rotation_id: Mapped[int] = mapped_column(ForeignKey("Rotation.id"), nullable=False)
    # """The unique identifier of the rotation. Foreign key to :attr:`Rotation.id`."""
    # rotation: Mapped["Rotation"] = relationship("Rotation", back_populates="trips")
    # """The rotation.""" #TODO: Enable

    departure_station_id: Mapped[int] = mapped_column(
        ForeignKey("Station.id"), nullable=False
    )
    """The unique identifier of the departure station. Foreign key to :attr:`Station.id`."""
    departure_station: Mapped[Station] = relationship(
        "Station", back_populates="trips_departing", foreign_keys=[departure_station_id]
    )
    """The departure station."""

    departure_time: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), nullable=False
    )
    """The departure time at the first station."""

    arrival_station_id: Mapped[int] = mapped_column(
        ForeignKey("Station.id"), nullable=False
    )
    """The unique identifier of the arrival station. Foreign key to :attr:`Station.id`."""
    arrival_station: Mapped[Station] = relationship(
        "Station", back_populates="trips_arriving", foreign_keys=[arrival_station_id]
    )
    """The arrival station."""

    arrival_time: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), nullable=False
    )
    """The arrival time at the last station."""

    trip_type = mapped_column(SqlEnum(TripType), nullable=False)
    """The type of the trip. Either `EMPTY` or `PASSENGER`."""

    level_of_loading = mapped_column(Float, nullable=True)
    """The level of loading of the bus. This is a mass in kg."""

    stop_times: Mapped[List["StopTime"]] = relationship(
        "StopTime", back_populates="trip"
    )

    # Create a check constraint to ensure that the arrival time is after the departure time.
    __table_args__ = (
        CheckConstraint(
            "arrival_time > departure_time",
            name="trip_arrival_after_departure_check",
        ),
    )


class StopTime(Base):
    """
    This represents a stop time of a :class:`Trip` at a :class:`Station`.

    A trip is not guaranteed to have any stop times, but it either has none (with only the arrival and departure
    times set) or every stop (including the first and last) has a stop time.
    """

    __tablename__ = "StopTime"

    id: Mapped[int] = mapped_column(BigInteger, primary_key=True)
    """The unique identifier of the battery type. Auto-incremented."""

    scenario_id: Mapped[int] = mapped_column(ForeignKey("Scenario.id"), nullable=False)
    """The unique identifier of the scenario. Foreign key to :attr:`Scenario.id`."""
    scenario: Mapped["Scenario"] = relationship("Scenario", back_populates="stop_times")
    """The scenario."""

    station_id: Mapped[int] = mapped_column(ForeignKey("Station.id"), nullable=False)
    """The unique identifier of the station. Foreign key to :attr:`Station.id`."""
    station: Mapped[Station] = relationship("Station", back_populates="stop_times")
    """The station."""

    trip_id: Mapped[int] = mapped_column(ForeignKey("Trip.id"), nullable=False)
    """The unique identifier of the trip. Foreign key to :attr:`Trip.id`."""
    trip: Mapped["Trip"] = relationship("Trip", back_populates="stop_times")
    """The trip."""

    ordinal: Mapped[int] = mapped_column(BigInteger, nullable=False)
    """The ordinal of the stop time. Starts at 0."""

    elapsed_distance: Mapped[float] = mapped_column(Float, nullable=False)
    """The distance that the bus has traveled at this stop time."""

    arrival_time: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), nullable=False
    )
    """The arrival time at the station."""

    dwell_time: Mapped[timedelta] = mapped_column(
        Interval, nullable=False, default=timedelta(seconds=0)
    )
    """The dwell time at the station. Defaults to 0 if unspecified."""
