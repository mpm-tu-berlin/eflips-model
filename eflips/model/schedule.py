from datetime import datetime, timedelta
from enum import auto, Enum as PyEnum
from typing import Any, List, TYPE_CHECKING

from sqlalchemy import (
    BigInteger,
    Boolean,
    CheckConstraint,
    DateTime,
    Enum as SqlEnum,
    event,
    Float,
    ForeignKey,
    Interval,
    Text,
    UniqueConstraint,
)
from sqlalchemy.orm import Mapped, mapped_column, relationship

from eflips.model import Base

if TYPE_CHECKING:
    from eflips.model import Event, Vehicle, VehicleType, Scenario, Station, Route


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
    station: Mapped["Station"] = relationship("Station", back_populates="stop_times")
    """The station."""

    trip_id: Mapped[int] = mapped_column(ForeignKey("Trip.id"), nullable=False)
    """The unique identifier of the trip. Foreign key to :attr:`Trip.id`."""
    trip: Mapped["Trip"] = relationship("Trip", back_populates="stop_times")
    """The trip."""

    arrival_time: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), nullable=False
    )
    """The arrival time at the station."""

    dwell_duration: Mapped[timedelta] = mapped_column(
        Interval, nullable=False, default=timedelta(seconds=0)
    )
    """The dwell time at the station. Defaults to 0 if unspecified."""

    __table_args__ = (
        # Dwell time must be positive
        CheckConstraint(
            "dwell_duration >= '0 seconds'",
            name="stop_time_dwell_duration_positive_check",
        ),
        UniqueConstraint(
            "trip_id", "arrival_time", name="stop_time_arrival_unique_constraint"
        ),
        UniqueConstraint("trip_id", "station_id", name="stop_trip_unique_constraint"),
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
    route: Mapped["Route"] = relationship("Route", back_populates="trips")
    """The route."""

    rotation_id: Mapped[int] = mapped_column(ForeignKey("Rotation.id"), nullable=False)
    """The unique identifier of the rotation. Foreign key to :attr:`Rotation.id`."""
    rotation: Mapped["Rotation"] = relationship("Rotation", back_populates="trips")
    """The rotation."""

    departure_time: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), nullable=False
    )
    """The departure time at the first station."""

    arrival_time: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), nullable=False
    )
    """The arrival time at the last station."""

    trip_type = mapped_column(SqlEnum(TripType), nullable=False)
    """The type of the trip. Either `EMPTY` or `PASSENGER`."""

    level_of_loading = mapped_column(Float, nullable=True)
    """The level of loading of the bus. This is a mass in kg."""

    stop_times: Mapped[List["StopTime"]] = relationship(
        "StopTime", back_populates="trip", order_by="StopTime.arrival_time"
    )

    stations = relationship(
        "Station", secondary="StopTime", order_by="StopTime.arrival_time", viewonly=True
    )
    """The stations of the trip."""

    events: Mapped[List["Event"]] = relationship("Event", back_populates="trip")

    # Create a check constraint to ensure that the arrival time is after the departure time.
    __table_args__ = (
        CheckConstraint(
            "arrival_time > departure_time",
            name="trip_arrival_after_departure_check",
        ),
    )


@event.listens_for(Trip, "before_insert")
@event.listens_for(Trip, "before_update")
def check_trip_before_commit(_: Any, __: Any, target: Trip) -> None:
    """
    Before a trip is flushed to the database, if it has stop times:
    - Ensure that the arrival time of the first stop time is the departure time of the trip
    - Ensure that the arrival time of the last stop time is the arrival time of the trip
    - Ensure that the first stop time is the first stop of the route
    - Ensure that the last stop time is the last stop of the route

    :param target: a trip
    :return: Nothing. Raises an exception if something is wrong.
    """
    # If the trip has stop times, check them
    if len(target.stop_times) > 0:
        sorted_stop_times = sorted(target.stop_times, key=lambda x: x.arrival_time)

        if sorted_stop_times[0].arrival_time != target.departure_time:
            raise ValueError(
                "The arrival time of the first stop time of a trip must be the departure time of the trip. "
                f"Trip {target.id} violates this."
            )
        if sorted_stop_times[-1].arrival_time != target.arrival_time:
            raise ValueError(
                "The arrival time of the last stop time of a trip must be the arrival time of the trip. "
                f"Trip {target.id} violates this."
            )

        # For the station, we need to take care to either confirm by ID or by object, depending on which is available
        if sorted_stop_times[0].station_id is not None:
            if sorted_stop_times[0].station_id != target.route.departure_station_id:
                raise ValueError(
                    "The first stop time of a trip must be the first stop of the route. "
                    f"Trip {target.id} violates this."
                )
        elif sorted_stop_times[0].station is not None:
            if sorted_stop_times[0].station != target.route.departure_station:
                raise ValueError(
                    "The first stop time of a trip must be the first stop of the route. "
                    f"Trip {target.id} violates this."
                )
        else:
            raise ValueError("The stop time of a trip must have a station.")

        if sorted_stop_times[-1].station_id is not None:
            if sorted_stop_times[-1].station_id != target.route.arrival_station_id:
                raise ValueError(
                    "The last stop time of a trip must be the last stop of the route. "
                    f"Trip {target.id} violates this."
                )
        elif sorted_stop_times[-1].station is not None:
            if sorted_stop_times[-1].station != target.route.arrival_station:
                raise ValueError(
                    "The last stop time of a trip must be the last stop of the route. "
                    f"Trip {target.id} violates this."
                )
        else:
            raise ValueError("The stop time of a trip must have a station.")

        # Check that the order of the stop times is the same as the order of the stations in the route
        if len(target.route.assoc_route_stations) > 0:
            sorted_route_stations = sorted(
                target.route.assoc_route_stations, key=lambda x: x.elapsed_distance
            )
            try:
                while len(sorted_stop_times) > 0:
                    # Get the next associated route station
                    assoc_route_station = sorted_route_stations.pop(0)

                    # Get the next stop time
                    stop_time = sorted_stop_times.pop(0)

                    # There may be associated route stations without stop times
                    if (
                        assoc_route_station.station_id is not None
                        and stop_time.station_id is not None
                    ):
                        while stop_time.station_id != assoc_route_station.station_id:
                            assoc_route_station = sorted_route_stations.pop(0)
                    elif (
                        assoc_route_station.station is not None
                        and stop_time.station is not None
                    ):
                        while stop_time.station != assoc_route_station.station:
                            assoc_route_station = sorted_route_stations.pop(0)
                    else:
                        raise ValueError("The stop time of a trip must have a station.")
            except IndexError as e:
                raise ValueError(
                    "The order of the stop times of a trip must be the same as the order of the stations in the route. "
                    f"Trip {target.id} violates this."
                ) from e


class Rotation(Base):
    """
    A rotation is a sequence of trips that are performed by a bus in a single day.
    """

    __tablename__ = "Rotation"

    id: Mapped[int] = mapped_column(BigInteger, primary_key=True)
    """The unique identifier of the battery type. Auto-incremented."""

    scenario_id: Mapped[int] = mapped_column(ForeignKey("Scenario.id"), nullable=False)
    """The unique identifier of the scenario. Foreign key to :attr:`Scenario.id`."""
    scenario: Mapped["Scenario"] = relationship("Scenario", back_populates="rotations")
    """The scenario."""

    vehicle_type_id: Mapped[int] = mapped_column(
        ForeignKey("VehicleType.id"), nullable=False
    )
    """The unique identifier of the vehicle type. Foreign key to :attr:`VehicleType.id`."""
    vehicle_type: Mapped["VehicleType"] = relationship(
        "VehicleType", back_populates="rotations"
    )
    """The vehicle type."""

    vehicle_id: Mapped[int] = mapped_column(ForeignKey("Vehicle.id"), nullable=True)
    """The unique identifier of the vehicle. Foreign key to :attr:`Vehicle.id`."""
    vehicle: Mapped["Vehicle"] = relationship("Vehicle", back_populates="rotations")

    allow_opportunity_charging: Mapped[bool] = mapped_column(Boolean, nullable=False)
    """
    Whether opportunity charging is permitted. To actually charge, the vehicle type must support opportunity charging.
    """

    name: Mapped[str] = mapped_column(Text, nullable=True)
    """The name of the rotation."""

    trips: Mapped[List["Trip"]] = relationship("Trip", back_populates="rotation")
    """A list of trips."""


@event.listens_for(Rotation, "before_insert")
@event.listens_for(Rotation, "before_update")
def check_rotation_before_commit(_: Any, __: Any, target: Rotation) -> None:
    """
    A Rotation needs to be contiguous in time and space
    - the end station of a trip must be the start station of the next trip
    - the departure time of a trip must be after the arrival time of the previous trip

    :param target: A Rotation object
    :return: Nothing. Raises an exception if something is wrong.
    """
    for i in range(len(target.trips) - 1):
        # Check for geographical continuity
        if (
            target.trips[i].route.arrival_station
            != target.trips[i + 1].route.departure_station
        ):
            raise ValueError(
                "The end station of a trip must be the start station of the next trip. "
                f"Rotation {target.id} violates this."
            )

        # Check for temporal continuity
        if target.trips[i].arrival_time > target.trips[i + 1].departure_time:
            raise ValueError(
                "The departure time of a trip must be after the arrival time of the previous trip. "
                f"Rotation {target.id} violates this."
            )
