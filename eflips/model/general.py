import uuid
from datetime import datetime
from enum import auto, Enum as PyEnum
from typing import Any, Dict, List, TYPE_CHECKING, Union

from sqlalchemy import (
    BigInteger,
    Boolean,
    CheckConstraint,
    Column,
    DateTime,
    Enum as SqlEnum,
    Float,
    ForeignKey,
    func,
    Integer,
    Text,
    UUID,
)
from sqlalchemy.dialects import postgresql
from sqlalchemy.dialects.postgresql import ExcludeConstraint
from sqlalchemy.orm import make_transient, Mapped, mapped_column, relationship, Session

from eflips.model import Base
from eflips.model.depot import AssocAreaProcess, AssocPlanProcess

if TYPE_CHECKING:
    from eflips.model import (
        Route,
        Line,
        Station,
        StopTime,
        Trip,
        AssocRouteStation,
        Rotation,
        Depot,
        Plan,
        Area,
        Process,
    )


class Scenario(Base):
    __tablename__ = "Scenario"

    id: Mapped[int] = mapped_column(BigInteger, primary_key=True)
    """The unique identifier of the scenario. Auto-incremented."""

    parent_id: Mapped[int] = mapped_column(ForeignKey("Scenario.id"), nullable=True)
    """The unique identifier of the parent scenario. Foreign key to :attr:`Scenario.id`."""
    parent: Mapped["Scenario"] = relationship(
        "Scenario", back_populates="children", remote_side=[id]
    )
    """The parent scenario."""
    children: Mapped[List["Scenario"]] = relationship(
        "Scenario", back_populates="parent"
    )
    """A list of child scenarios."""

    name: Mapped[str] = mapped_column(Text)
    """A name for the scenario."""
    name_short: Mapped[str] = mapped_column(Text, nullable=True)
    """An optional short name for the scenario."""
    created: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), server_default=func.now()
    )
    """The time the scenario was created. Automatically set to the current time at creation."""
    finished: Mapped[datetime] = mapped_column(DateTime(timezone=True), nullable=True)
    """
    The time the simulation was finished. Automatically set to the current time at simulation end. Null if not yet 
    finished.
    """
    simba_options: Mapped[Dict[str, Any]] = mapped_column(
        postgresql.JSONB, nullable=True
    )
    """The options for the simBA simulation. Stored as a JSON object."""
    eflips_depot_options: Mapped[Dict[str, Any]] = mapped_column(
        postgresql.JSONB, nullable=True
    )
    """The options for the eflips-depot simulation. Stored as a JSON object."""
    task_id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True), nullable=True, unique=True
    )
    """The task id of the simulation. Automatically set to a UUID when a scenario is submitted for simulation."""

    # Most of the other columns (all except the Assoc-Tables for many-to-many relationships) have the scenario_id
    # as a foreign key. They are mapped below.
    vehicle_types: Mapped[List["VehicleType"]] = relationship(
        "VehicleType", back_populates="scenario", cascade="all, delete"
    )
    """A list of vehicle types."""
    battery_types: Mapped[List["BatteryType"]] = relationship(
        "BatteryType", back_populates="scenario", cascade="all, delete"
    )
    """A list of battery types."""

    vehicles: Mapped[List["Vehicle"]] = relationship(
        "Vehicle", back_populates="scenario", cascade="all, delete"
    )
    """A list of vehicles."""

    vehicle_classes: Mapped[List["VehicleClass"]] = relationship(
        "VehicleClass", back_populates="scenario", cascade="all, delete"
    )
    lines: Mapped[List["Line"]] = relationship(
        "Line", back_populates="scenario", cascade="all, delete"
    )
    """A list of lines."""
    routes: Mapped[List["Route"]] = relationship(
        "Route", back_populates="scenario", cascade="all, delete"
    )
    """A list of routes."""
    stations: Mapped[List["Station"]] = relationship(
        "Station", back_populates="scenario", cascade="all, delete"
    )
    assoc_route_stations: Mapped[List["AssocRouteStation"]] = relationship(
        "AssocRouteStation", back_populates="scenario", cascade="all, delete"
    )
    """A list of stations."""
    stop_times: Mapped[List["StopTime"]] = relationship(
        "StopTime", back_populates="scenario", cascade="all, delete"
    )
    """A list of stop times."""
    trips: Mapped[List["Trip"]] = relationship(
        "Trip", back_populates="scenario", cascade="all, delete"
    )
    """A list of trips."""
    rotations: Mapped[List["Rotation"]] = relationship(
        "Rotation", back_populates="scenario", cascade="all, delete"
    )
    """A list of events."""
    events: Mapped[List["Event"]] = relationship(
        "Event", back_populates="scenario", cascade="all, delete"
    )
    depots: Mapped[List["Depot"]] = relationship(
        "Depot", back_populates="scenario", cascade="all, delete"
    )
    """A list of depots."""

    plans: Mapped[List["Plan"]] = relationship(
        "Plan", back_populates="scenario", cascade="all, delete"
    )
    """A list of plans."""

    areas: Mapped[List["Area"]] = relationship(
        "Area", back_populates="scenario", cascade="all, delete"
    )
    """A list of areas."""

    processes: Mapped[List["Process"]] = relationship(
        "Process", back_populates="scenario", cascade="all, delete"
    )
    """A list of processes."""
    assoc_plan_processes: Mapped[List["AssocPlanProcess"]] = relationship(
        "AssocPlanProcess", back_populates="scenario", cascade="all, delete"
    )

    @staticmethod
    def _copy_object(obj: Any, session: Session, scenario: "Scenario") -> None:
        """
        Internal helper function to copy an SQLAlchemy object and attach it to a new scenario.
        :param obj: An SQLAlchemy object. Must have an 'id' attribute and a 'scenario' attribute.
        :param session: an SQLAlchemy session.
        :return: The new object, attached to the new scenario.
        """
        make_transient(obj)
        obj.id = None
        obj.scenario = scenario
        session.add(obj)

    def clone(self, session: Session) -> "Scenario":
        """
        Creates a copy of the scenario, including all vehicle types and battery types.
        :param session: The database session.
        :return: The copy of the scenario.
        """
        scenario_copy = Scenario(
            name=self.name,
            name_short=self.name_short,
            simba_options=self.simba_options,
            eflips_depot_options=self.eflips_depot_options,
        )
        scenario_copy.parent = self
        session.add(scenario_copy)

        # For each type of relationship, we need to
        # Go through the entries on the "many" side of the relationship
        # Create a copy of the entry
        # Add it, flush it, note the new id in the id_map
        with session.no_autoflush:
            vehicle_type_id_map: Dict[int, VehicleType] = {}
            for vehicle_type in self.vehicle_types:
                original_id = vehicle_type.id
                self._copy_object(vehicle_type, session, scenario_copy)
                vehicle_type_id_map[original_id] = vehicle_type

            battery_type_id_map: Dict[int, BatteryType] = {}
            for battery_type in self.battery_types:
                original_id = battery_type.id
                self._copy_object(battery_type, session, scenario_copy)
                battery_type_id_map[original_id] = battery_type

            vehicle_id_map: Dict[int, Vehicle] = {}
            for vehicle in self.vehicles:
                original_id = vehicle.id
                self._copy_object(vehicle, session, scenario_copy)
                vehicle_id_map[original_id] = vehicle

            vehicle_class_id_map: Dict[int, VehicleClass] = {}
            for vehicle_class in self.vehicle_classes:
                original_id = vehicle_class.id
                self._copy_object(vehicle_class, session, scenario_copy)
                vehicle_class_id_map[original_id] = vehicle_class

            line_id_map: Dict[int, "Line"] = {}
            for line in self.lines:
                original_id = line.id
                self._copy_object(line, session, scenario_copy)
                line_id_map[original_id] = line

            route_id_map: Dict[int, "Route"] = {}
            for route in self.routes:
                original_id = route.id
                self._copy_object(route, session, scenario_copy)
                route_id_map[original_id] = route

            station_id_map: Dict[int, "Station"] = {}
            for station in self.stations:
                original_id = station.id
                self._copy_object(station, session, scenario_copy)
                station_id_map[original_id] = station

            route_station_id_map: Dict[int, "AssocRouteStation"] = {}
            for route_station in self.assoc_route_stations:
                original_id = route_station.id
                self._copy_object(route_station, session, scenario_copy)
                route_station_id_map[original_id] = route_station

            trip_id_map: Dict[int, "Trip"] = {}
            for trip in self.trips:
                original_id = trip.id
                self._copy_object(trip, session, scenario_copy)
                trip_id_map[original_id] = trip

            rotation_id_map: Dict[int, "Rotation"] = {}
            for rotation in self.rotations:
                original_id = rotation.id
                self._copy_object(rotation, session, scenario_copy)
                rotation_id_map[original_id] = rotation

            event_id_map: Dict[int, "Event"] = {}
            for event in self.events:
                original_id = event.id
                self._copy_object(event, session, scenario_copy)
                event_id_map[original_id] = event

            depot_id_map: Dict[int, "Depot"] = {}
            for depot in self.depots:
                original_id = depot.id
                self._copy_object(depot, session, scenario_copy)
                depot_id_map[original_id] = depot

            plan_id_map: Dict[int, "Plan"] = {}
            for plan in self.plans:
                original_id = plan.id
                self._copy_object(plan, session, scenario_copy)
                plan_id_map[original_id] = plan

            area_id_map: Dict[int, "Area"] = {}
            for area in self.areas:
                original_id = area.id
                self._copy_object(area, session, scenario_copy)
                area_id_map[original_id] = area

            process_id_map: Dict[int, "Process"] = {}
            for process in self.processes:
                original_id = process.id
                self._copy_object(process, session, scenario_copy)
                process_id_map[original_id] = process

            assoc_plan_process_id_map: Dict[int, "AssocPlanProcess"] = {}
            for assoc_plan_process in self.assoc_plan_processes:
                original_id = assoc_plan_process.id
                self._copy_object(assoc_plan_process, session, scenario_copy)
                assoc_plan_process_id_map[original_id] = assoc_plan_process

        # This assigns the new ids
        session.flush()

        # Now that we have copied every object, we need to update their relationships among each other.
        # At least for those that have foreign keys.
        for vehicle_type in scenario_copy.vehicle_types:
            if vehicle_type.battery_type_id is not None:
                vehicle_type.battery_type_id = battery_type_id_map[
                    vehicle_type.battery_type_id
                ].id

        # BatteryType has no foreign keys, so we don't need to update anything there.

        # Vehicle <-> VehicleType
        for vehicle in scenario_copy.vehicles:
            vehicle.vehicle_type_id = vehicle_type_id_map[vehicle.vehicle_type_id].id

        # VehicleType <-> VehicleClass many-to-many by updating the association table
        for entry in session.query(AssocVehicleTypeVehicleClass):
            if (
                entry.vehicle_type_id in vehicle_type_id_map
                and entry.vehicle_class_id in vehicle_class_id_map
            ):
                new_entry = AssocVehicleTypeVehicleClass(
                    vehicle_type_id=vehicle_type_id_map[entry.vehicle_type_id].id,
                    vehicle_class_id=vehicle_class_id_map[entry.vehicle_class_id].id,
                )
                session.add(new_entry)
            elif (
                entry.vehicle_type_id not in vehicle_type_id_map
                and entry.vehicle_class_id in vehicle_class_id_map
            ):
                pass
            else:
                raise ValueError(
                    "There exists an association between a vehicle type and a vehicle class that is not in"
                    " the scenario."
                )

        # Line <-> Route
        for route in scenario_copy.routes:
            if route.line_id is not None:
                route.line_id = line_id_map[route.line_id].id

        # Route <-> Station
        for route in scenario_copy.routes:
            route.departure_station_id = station_id_map[route.departure_station_id].id
            route.arrival_station_id = station_id_map[route.arrival_station_id].id

        # Route <-> AssocRouteStation <-> Station
        for route_station in scenario_copy.assoc_route_stations:
            if route_station.route.scenario_id != scenario_copy.id:
                route_station.route_id = route_id_map[route_station.route_id].id
            route_station.station_id = station_id_map[route_station.station_id].id

        # Station <-> StopTime, trips_departing, trips_arriving
        for station in scenario_copy.stations:
            for stop_time in station.stop_times:
                stop_time.station_id = station_id_map[stop_time.station_id].id

        # Trip <-> Route
        for trip in scenario_copy.trips:
            trip.route_id = route_id_map[trip.route_id].id

        # Trip <-> Rotation
        for trip in scenario_copy.trips:
            trip.rotation_id = rotation_id_map[trip.rotation_id].id

        # Trip <-> StopTime
        for trip in scenario_copy.trips:
            for stop_time in trip.stop_times:
                stop_time.trip_id = trip_id_map[stop_time.trip_id].id

        # Rotation <-> VehicleType
        for rotation in scenario_copy.rotations:
            rotation.vehicle_type_id = vehicle_type_id_map[rotation.vehicle_type_id].id

        # Rotation <-> Vehicle
        for rotation in scenario_copy.rotations:
            if rotation.vehicle_id is not None:
                rotation.vehicle_id = vehicle_id_map[rotation.vehicle_id].id

        # Event <-> VehicleType
        for event in scenario_copy.events:
            if event.vehicle_type_id is not None:
                event.vehicle_type_id = vehicle_type_id_map[event.vehicle_type_id].id

        # Depot <-> Plan
        for depot in scenario_copy.depots:
            depot.default_plan_id = plan_id_map[depot.default_plan_id].id

        # Area <-> Depot, VehicleType
        for area in scenario_copy.areas:
            area.depot_id = depot_id_map[area.depot_id].id
            area.vehicle_type_id = vehicle_type_id_map[area.vehicle_type_id].id

        # Process <-> Area is a many-to-many relationship, so we need to update the association table
        for area_process_entry in session.query(AssocAreaProcess):
            if (
                area_process_entry.area_id in area_id_map
                and area_process_entry.process_id in process_id_map
            ):
                new_area_process_entry = AssocAreaProcess(
                    area_id=area_id_map[area_process_entry.area_id].id,
                    process_id=process_id_map[area_process_entry.process_id].id,
                )
                session.add(area_process_entry)
            elif (
                area_process_entry.area_id not in area_id_map
                and area_process_entry.process_id in process_id_map
            ):
                pass
            else:
                raise ValueError(
                    "There exists an association between an area and a process that is not in"
                    " the scenario."
                )

        # AssocPlanProcess <-> Plan, Process
        # For some reason, here we need to create new AssocPlanProcess for the old scenario objects instead of just
        # updating the ids.
        for plan_process_entry in scenario_copy.assoc_plan_processes:
            plan_process_entry.plan_id = plan_id_map[plan_process_entry.plan_id].id
            plan_process_entry.process_id = process_id_map[
                plan_process_entry.process_id
            ].id
        session.flush()
        return scenario_copy


class VehicleType(Base):
    """
    This class represents a vehicle type, containing the technical parameters shared by all vehicles of this type.
    It is used by vehicles (which are of a specific type) and by the rotations (which are for specific vehicle types).
    """

    __tablename__ = "VehicleType"
    _table_args_list = []

    id: Mapped[int] = mapped_column(BigInteger, primary_key=True)
    """The unique identifier of the vehicle type. Auto-incremented."""

    scenario_id: Mapped[int] = mapped_column(ForeignKey("Scenario.id"))
    """The unique identifier of the scenario. Foreign key to :attr:`Scenario.id`."""
    scenario: Mapped[Scenario] = relationship(
        "Scenario", back_populates="vehicle_types"
    )
    """The scenario."""

    battery_type_id: Mapped[int] = mapped_column(
        ForeignKey("BatteryType.id"), nullable=True
    )
    """The unique identifier of the battery type. Foreign key to :attr:`BatteryType.id`."""
    battery_type: Mapped["BatteryType"] = relationship(
        "BatteryType", back_populates="vehicle_types"
    )
    """The battery type."""

    name: Mapped[str] = mapped_column(Text)
    """A name for the vehicle type."""
    name_short: Mapped[str] = mapped_column(Text, nullable=True)
    """An optional short name for the vehicle type."""

    battery_capacity: Mapped[float] = mapped_column(Float)
    """The battery capacity in kWh. This refers to the usable capacity, not the total capacity."""
    battery_capacity_constraint = CheckConstraint("battery_capacity > 0")
    _table_args_list.append(battery_capacity_constraint)

    battery_capacity_reserve: Mapped[float] = mapped_column(
        Float, nullable=False, server_default="0.0"
    )
    """The battery capacity reserve below 0 kWh 'capacity' in kWh. Using this value in generating evaluation, 
    things such as "always 10% reserve" can be modeled."""
    battery_capacity_reserve_constraint = CheckConstraint(
        "battery_capacity_reserve >= 0"
    )
    _table_args_list.append(battery_capacity_reserve_constraint)

    charging_curve: Mapped[List[List[float]]] = mapped_column(
        postgresql.ARRAY(Float, dimensions=2)
    )
    """
    The charging curve of the vehicle type. This is a 2D array of floats with two rows. The first row contains
    the state of charge, ranging from 0 (or some negative value if there is a nonzero reserve) to 1. The second row
    contains the charging power in kW. The charging curve is used to calculate the charging power of a vehicle
    using linear interpolation. The charging curve must be monotonically increasing in the first row.
    """

    v2g_curve: Mapped[List[List[float]]] = mapped_column(
        postgresql.ARRAY(Float, dimensions=2), nullable=True
    )
    """
    The vehicle-to-grid curve of the vehicle type. This is a 2D array of floats with two rows. The first row contains
    the state of charge, ranging from 0 to 1. The second row contains the discharging power in kW. The v2g curve is
    used to calculate the discharging power of a vehicle using linear interpolation. The v2g curve must be monotonically
    increasing in the first row. It may bo None if the vehicle type does not support vehicle-to-grid.
    """

    charging_efficiency: Mapped[float] = mapped_column(Float, server_default="0.95")
    """Ratio of battery output (while driving/V2G) to grid input. Also applies to V2G."""
    charging_efficiency_constraint_lower = CheckConstraint("charging_efficiency > 0")
    _table_args_list.append(charging_efficiency_constraint_lower)
    charging_efficiency_constraint_upper = CheckConstraint("charging_efficiency <= 1")
    _table_args_list.append(charging_efficiency_constraint_upper)

    opportunity_charging_capable: Mapped[bool] = mapped_column(Boolean)
    """
    Whether the bus is capable of automatic highpower charging. All buses are assumed to be capable of (depot) 
    conductive charging.
    """

    minimum_charging_power: Mapped[float] = mapped_column(Float, server_default="0.0")
    """If the charging power falls below this value, charging is canceled"""
    minimum_charging_power_constraint = CheckConstraint("minimum_charging_power >= 0")
    _table_args_list.append(minimum_charging_power_constraint)

    # Shape is specified in length, width, height
    length: Mapped[float] = mapped_column(Float, nullable=True)
    """The length of the vehicle in meters."""

    width: Mapped[float] = mapped_column(Float, nullable=True)
    """The width of the vehicle in meters."""

    height: Mapped[float] = mapped_column(Float, nullable=True)
    """The height of the vehicle in meters."""

    # Length, width, and height must either all be None or all be not None
    _table_args_list.append(
        CheckConstraint(
            "(length IS NULL AND width IS NULL AND height IS NULL) OR "
            "(length IS NOT NULL AND width IS NOT NULL AND height IS NOT NULL)"
        )
    )

    empty_mass: Mapped[float] = mapped_column(Float, nullable=True)
    """The empty mass of the vehicle in kg."""
    empty_mass_constraint = CheckConstraint("empty_mass > 0")
    _table_args_list.append(empty_mass_constraint)

    consumption: Mapped[float] = mapped_column(Float, nullable=True)
    """
    The vehicle's energy consumption in kWh/km. This is used to calculate the energy consumption of a trip. Can
    be None if we are using more detailed consumption models.
    """

    vehicles: Mapped[List["Vehicle"]] = relationship(
        "Vehicle", back_populates="vehicle_type"
    )
    """A list of vehicles."""

    vehicle_classes: Mapped[List["VehicleClass"]] = relationship(
        "VehicleClass",
        secondary="AssocVehicleTypeVehicleClass",
        back_populates="vehicle_types",
    )
    """A list of vehicle classes."""

    rotations: Mapped[List["Rotation"]] = relationship(
        "Rotation", back_populates="vehicle_type"
    )
    """A list of rotations."""

    events: Mapped[List["Event"]] = relationship("Event", back_populates="vehicle_type")
    """A list of events."""

    areas: Mapped[List["Area"]] = relationship("Area", back_populates="vehicle_type")
    """A list of areas."""

    __table_args__ = tuple(_table_args_list)


class BatteryType(Base):
    __tablename__ = "BatteryType"

    id: Mapped[int] = mapped_column(BigInteger, primary_key=True)
    """The unique identifier of the battery type. Auto-incremented."""

    scenario_id: Mapped[int] = mapped_column(ForeignKey("Scenario.id"), nullable=False)
    """The unique identifier of the scenario. Foreign key to :attr:`Scenario.id`."""
    scenario: Mapped[Scenario] = relationship(
        "Scenario", back_populates="battery_types"
    )
    """The scenario."""

    vehicle_types: Mapped[List["VehicleType"]] = relationship(
        "VehicleType", back_populates="battery_type"
    )

    specific_mass: Mapped[float] = mapped_column(Float)
    """The specific mass of the battery in kg/kWh. Relative to gross (not net) capacity."""

    chemistry: Mapped[Dict[str, Any]] = mapped_column(postgresql.JSONB)
    """The chemistry of the battery. Stored as a JSON object, defined by eflips-LCA"""


class Vehicle(Base):
    """
    A vehicle is a concrete vehicle of a certain type.
    """

    __tablename__ = "Vehicle"

    id: Mapped[int] = mapped_column(BigInteger, primary_key=True)
    """The unique identifier of the battery type. Auto-incremented."""

    scenario_id: Mapped[int] = mapped_column(ForeignKey("Scenario.id"), nullable=False)
    """The unique identifier of the scenario. Foreign key to :attr:`Scenario.id`."""
    scenario: Mapped[Scenario] = relationship("Scenario", back_populates="vehicles")
    """The scenario."""

    vehicle_type_id: Mapped[int] = mapped_column(
        ForeignKey("VehicleType.id"), nullable=False
    )
    """The unique identifier of the vehicle type. Foreign key to :attr:`VehicleType.id`."""
    vehicle_type: Mapped[VehicleType] = relationship(
        "VehicleType", back_populates="vehicles"
    )
    """The vehicle type."""

    name: Mapped[str] = mapped_column(Text)
    """A name for the vehicle."""

    name_short: Mapped[str] = mapped_column(Text, nullable=True)
    """An optional short name for the vehicle."""

    rotations: Mapped[List["Rotation"]] = relationship(
        "Rotation", back_populates="vehicle"
    )
    """A list of rotations this vehicle is used for."""

    events: Mapped[List["Event"]] = relationship("Event", back_populates="vehicle")


class VehicleClass(Base):
    """
    VehicleClasses allow a many-to-many relationship between vehicles and classes, which may be used for specifying
    things such as "any 12m bus" or "any 18m bus".

    The VehicleClass table is not used directly, but through the association table AssocVehicleTypeVehicleClass.

    **Support is currently incomplete. THis only exists as a stub (and is used by eflip-LCA), but is not implemented
    in django.simba or eflips-depot**
    """

    __tablename__ = "VehicleClass"

    id: Mapped[int] = mapped_column(BigInteger, primary_key=True)
    """The unique identifier of the battery type. Auto-incremented."""

    scenario_id: Mapped[int] = mapped_column(ForeignKey("Scenario.id"), nullable=False)
    """The unique identifier of the scenario. Foreign key to :attr:`Scenario.id`."""
    scenario: Mapped[Scenario] = relationship(
        "Scenario", back_populates="vehicle_classes"
    )
    """The scenario."""

    name: Mapped[str] = mapped_column(Text)
    """A name for the vehicle class."""

    name_short: Mapped[str] = mapped_column(Text, nullable=True)
    """An optional short name for the vehicle class."""

    vehicle_types: Mapped[List["VehicleType"]] = relationship(
        "VehicleType",
        secondary="AssocVehicleTypeVehicleClass",
        back_populates="vehicle_classes",
    )


class AssocVehicleTypeVehicleClass(Base):
    """
    The association table for the many-to-many relationship between vehicles and classes.
    """

    __tablename__ = "AssocVehicleTypeVehicleClass"
    id = mapped_column(BigInteger, primary_key=True)
    """Not the primary key and not used in SQLAlchemy, but required by Django."""

    vehicle_type_id: Mapped[int] = mapped_column(ForeignKey("VehicleType.id"))
    """The unique identifier of the vehicle type. Foreign key to :attr:`VehicleType.id`."""

    vehicle_class_id: Mapped[int] = mapped_column(ForeignKey("VehicleClass.id"))
    """The unique identifier of the vehicle class. Foreign key to :attr:`VehicleClass.id`."""


class EventType(PyEnum):
    """
    The EventType can be used to filter for certain types of events. It is also used to determine the valid combinations
    of nullable fields in the Event table.
    """

    DRIVING = auto()
    """Driving on a trip."""

    CHARGING_OPPORTUNITY = auto()
    """Charging at a terminal station."""

    CHARGING_DEPOT = auto()
    """Charging at a depot."""

    SERVICE = auto()
    """Service at a depot. Probably, the description field should be used to specify the type of service."""

    STANDBY_DEPARTURE = auto()
    """Ready for departure from a depot."""

    PRECONDITIONING = auto()
    """HVAC is turned on using grid power."""


class Event(Base):
    """
    An Event represents a signle event in the simulation. This does not necessary mean a point in time, but a process
    during which something happens. For example, there are charging and driving events. Events are used to track the
    state of the simulation. They are also the basis for the evaluation of the simulation.

    Note that there are only certain valid combinations of the nullable fields.
    An event can take place either at a
    - station (station_id is not null and subloc_no is not null). Possible events: CHARGING_OPPORTUNITY
    - depot (station_id is not null and subloc_no is null). Possible events: CHARGING_DEPOT, SERVICE, STANDBY_DEPARTURE
    PRECONDITIONING
    - trip (trip_id is not null and subloc_no is null). Possible events: DRIVING


    """

    __tablename__ = "Event"

    id: Mapped[int] = mapped_column(BigInteger, primary_key=True)
    """The unique identifier of the event. Auto-incremented."""

    scenario_id: Mapped[int] = mapped_column(ForeignKey("Scenario.id"), nullable=False)
    """The unique identifier of the scenario. Foreign key to :attr:`Scenario.id`."""
    scenario: Mapped[Scenario] = relationship("Scenario", back_populates="events")
    """The scenario."""

    vehicle_type_id: Mapped[int] = mapped_column(
        ForeignKey("VehicleType.id"), nullable=False
    )
    """The unique identifier of the vehicle type. Foreign key to :attr:`VehicleType.id`."""
    vehicle_type: Mapped[VehicleType] = relationship(
        "VehicleType", back_populates="events"
    )

    vehicle_id: Mapped[int] = mapped_column(ForeignKey("Vehicle.id"), nullable=True)
    """The unique identifier of the vehicle. Foreign key to :attr:`Vehicle.id`."""
    vehicle: Mapped["Vehicle"] = relationship("Vehicle", back_populates="events")
    """The vehicle."""

    station_id: Mapped[int] = mapped_column(ForeignKey("Station.id"), nullable=True)
    """The unique identifier of the station. Foreign key to :attr:`Station.id`."""
    station: Mapped["Station"] = relationship("Station", back_populates="events")

    area_id: Mapped[int] = mapped_column(ForeignKey("Area.id"), nullable=True)
    """The unique identifier of the area in the depot. Foreign key to :attr:`Area.id`."""
    area: Mapped["Area"] = relationship("Area", back_populates="events")

    subloc_no: Mapped[int] = mapped_column(Integer, nullable=True)
    """
    The number of the sub-location in the depot or multi-chargpoint terminal. The mapping of sub-locations to
    physical locations is defined by the depot layout and/or the multi-chargpoint terminal layout.
    """

    trip_id: Mapped[int] = mapped_column(ForeignKey("Trip.id"), nullable=True)
    """The unique identifier of the trip. Foreign key to :attr:`Trip.id`."""
    trip: Mapped["Trip"] = relationship("Trip", back_populates="events")

    time_start: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), nullable=False
    )
    """The time the event starts."""

    time_end: Mapped[datetime] = mapped_column(DateTime(timezone=True), nullable=False)
    """The time the event ends."""

    soc_start: Mapped[float] = mapped_column(Float, nullable=False)
    """
    The state of charge at the start of the event. This should refer to the net battery capacity.
    """

    soc_end: Mapped[float] = mapped_column(Float, nullable=False)
    """The state of charge at the end of the event. This should refer to the net battery capacity."""

    event_type: Mapped[EventType] = mapped_column(SqlEnum(EventType), nullable=False)
    """The type of the event."""

    description: Mapped[str] = mapped_column(Text, nullable=True)
    """A description of the event. Used to display additional information to the user."""

    timeseries: Mapped[Dict[str, List[Union[datetime, str, float]]]] = mapped_column(
        postgresql.JSONB, nullable=True
    )
    """
    Dict with mandatory keys „time“ (ISO 18601 with TZ), „soc“ (0-1) and optional keys „distance“ (m, along route for 
    trip) + other freely defined keys. Array of same length for each key
    """

    __table_args__ = (
        ExcludeConstraint(  # type: ignore
            (Column("scenario_id"), "="),
            (Column("vehicle_id"), "="),
            (func.tstzrange(Column("time_start"), Column("time_end"), "[]"), "&&"),
            name="scenario_id_time_range_excl",
            using="gist",
        ),
        CheckConstraint("soc_start >= 0"),
        CheckConstraint("soc_end >= 0"),
        CheckConstraint("soc_start <= 1"),
        CheckConstraint("soc_end <= 1"),
        # Also make sure the event type is valid for the nullable fields
        CheckConstraint(
            "(station_id IS NOT NULL AND subloc_no IS NOT NULL AND event_type IN ('CHARGING_OPPORTUNITY')) OR "
            "(area_id IS NOT NULL AND subloc_no IS NOT NULL AND event_type IN ('CHARGING_DEPOT', 'SERVICE', 'STANDBY_DEPARTURE', 'PRECONDITIONING')) OR "
            "(trip_id IS NOT NULL AND subloc_no IS NULL AND event_type IN ('DRIVING'))",
            name="filled_fields_type_combination",
        ),
    )
