import uuid
import warnings
from datetime import datetime, timedelta
from enum import auto, Enum as PyEnum
from itertools import product
from typing import Any, Dict, List, TYPE_CHECKING, Union

import numpy as np
import pandas as pd
from sqlalchemy import (
    Uuid,
    BigInteger,
    Boolean,
    CheckConstraint,
    DateTime,
    Enum as SqlEnum,
    event,
    Float,
    ForeignKey,
    func,
    inspect as sa_inspect,
    Integer,
    Text,
    UniqueConstraint,
    Index,
    JSON,
    PickleType,
    DDL,
)
from sqlalchemy.dialects import postgresql
from sqlalchemy.orm import (
    Mapped,
    mapped_column,
    relationship,
    Session,
)

from eflips.model import Base, ConsistencyWarning, TimeStampWithTz
from eflips.model.depot import AssocAreaProcess

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
        AssocPlanProcess,
    )


class ScenarioType(PyEnum):
    """Classifies a scenario by its provenance: original input, derived mutation, or simulation result."""

    SOURCE = auto()
    MUTATION = auto()
    SIMULATION = auto()


class Scenario(Base):
    __tablename__ = "Scenario"

    id: Mapped[int] = mapped_column(
        BigInteger().with_variant(Integer, "sqlite"), primary_key=True
    )
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

    scenario_type: Mapped[ScenarioType] = mapped_column(
        SqlEnum(ScenarioType, native_enum=False), nullable=True
    )
    """
    The type of Scenario. Used by django-simba.
    """

    name: Mapped[str] = mapped_column(Text)
    """A name for the scenario."""
    name_short: Mapped[str] = mapped_column(Text, nullable=True)
    """An optional short name for the scenario."""

    description: Mapped[str] = mapped_column(Text, nullable=True)
    """An optional description for the scenario. Can be used to store additional information about the scenario."""

    created: Mapped[datetime] = mapped_column(
        DateTime(timezone=True).with_variant(TimeStampWithTz, "sqlite"),
        server_default=func.now(),
    )
    """The time the scenario was created. Automatically set to the current time at creation."""
    finished: Mapped[datetime] = mapped_column(
        DateTime(timezone=True).with_variant(TimeStampWithTz, "sqlite"), nullable=True
    )
    """
    The time the simulation was finished. Automatically set to the current time at simulation end. Null if not yet 
    finished.
    """
    default_simba_options: str = '{"eta": false, "days": null, "mode": ["sim", "report"], "seed": 1, "config": null, "margin": 1, "logfile": "", "interval": 1, "loglevel": "INFO", "strategy": "distributed", "show_plots": false, "skip_plots": true, "cs_power_opps": 300, "gc_power_deps": 100000, "gc_power_opps": 100000, "input_schedule": null, "PRICE_THRESHOLD": -100, "rotation_filter": null, "signal_time_dif": 10, "cost_calculation": false, "desired_soc_deps": 1.0, "desired_soc_opps": 1.0, "optimizer_config": null, "output_directory": "data/sim_outputs", "include_price_csv": null, "min_charging_time": 0, "station_data_path": null, "ALLOW_NEGATIVE_SOC": true, "cs_power_deps_depb": 150, "cs_power_deps_oppb": 150, "vehicle_types_path": "data/examples/vehicle_types.json", "cost_parameters_file": null, "electrified_stations": null, "default_voltage_level": "MV", "propagate_mode_errors": false, "min_recharge_deps_depb": 1, "min_recharge_deps_oppb": 1, "preferred_charging_type": "depb", "default_buffer_time_opps": 0, "include_price_csv_option": [], "rotation_filter_variable": null, "check_rotation_consistency": false, "skip_inconsistent_rotations": false, "level_of_loading_over_day_path": null, "outside_temperature_over_day_path": null}'
    simba_options: Mapped[Dict[str, Any]] = mapped_column(
        postgresql.JSONB().with_variant(JSON, "sqlite"),  # type: ignore
        nullable=False,
        server_default=default_simba_options,
    )
    """The options for the simBA simulation. Stored as a JSON object."""
    eflips_depot_options: Mapped[Dict[str, Any]] = mapped_column(
        postgresql.JSONB().with_variant(JSON, "sqlite"), nullable=True  # type: ignore
    )
    """The options for the eflips-depot simulation. Stored as a JSON object."""
    task_id: Mapped[uuid.UUID] = mapped_column(
        Uuid,
        nullable=False,
        unique=True,
        default=uuid.uuid4,
    )
    """The task id of the simulation. Automatically set to a UUID when a scenario is submitted for simulation."""

    manager_id: Mapped[int] = mapped_column(Integer, nullable=True)
    """The unique identifier of the manager. Only used in the `django.simba` project."""

    tco_parameters: Mapped[Dict[str, Any]] = mapped_column(
        postgresql.JSONB().with_variant(JSON, "sqlite"),  # type: ignore
        nullable=True,
        server_default="""
            {
            "project_duration": 20,
            "interest_rate": 0.04,
            "inflation_rate": 0.02,
            "staff_cost": 30.0,
            "energy_cost": 0.18,
            "fuel_cost": 1.5,
            "maint_cost": 0.07,
            "maint_cost_diesel": 0.14,
            "maint_infr_cost": 1000.0,
            "taxes": 0.0,
            "insurance": 0.0,
            "pef_general": 0.02,
            "pef_wages": 0.025,
            "pef_energy": 0.038,
            "pef_insurance": 0.02
        }
            """,
    )
    """
    The TCO (Total Cost of Ownership) parameters for the scenario analysis.
    Stored as a JSON object containing the following parameters:

    Financial Parameters:
    - project_duration: Analysis period in years
    - interest_rate: Interest rate (value between 0 and 1)
    - inflation_rate: General inflation rate (value between 0 and 1)

    Cost Parameters:
    - staff_cost: Cost per staff member per hour
    - energy_cost: Cost per kWh of energy
    - maint_cost: Maintenance cost per vehicle per kilometer
    - maint_infr_cost: Maintenance cost per charging point and year
    - taxes: Tax cost per vehicle and year
    - insurance: Insurance cost per vehicle

    Price Escalation Factors (PEF):
    - pef_general: General price escalation factor (value between 0 and 1)
    - pef_wages: Wage price escalation factor (value between 0 and 1)
    - pef_energy: Energy price escalation factor (value between 0 and 1)
    - pef_insurance: Insurance price escalation factor (value between 0 and 1)

    Note: Cost parameters can be set to null if not applicable to the analysis.
    Price escalation factors represent annual cost increase rates, not relative to inflation.
    """

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
    consumption_luts: Mapped[List["ConsumptionLut"]] = relationship(
        "ConsumptionLut", back_populates="scenario", cascade="all, delete"
    )
    temperatures: Mapped[List["Temperatures"]] = relationship(
        "Temperatures", back_populates="scenario", cascade="all, delete"
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
    charging_point_types: Mapped[List["ChargingPointType"]] = relationship(
        "ChargingPointType", back_populates="scenario", cascade="all, delete"
    )
    """A list of charging point types."""

    @staticmethod
    def _copy_object(obj: Any, session: Session, scenario: "Scenario") -> Any:
        """
        Creates a copy of an SQLAlchemy object and attaches it to a new scenario.
        The original object is left completely unchanged in the session.
        :param obj: An SQLAlchemy object. Must have an 'id' and a 'scenario_id' attribute.
        :param session: An SQLAlchemy session.
        :param scenario: The new scenario to attach the copy to.
        :return: The newly created copy, pending in the session.
        """
        obj_copy = type(obj)()
        for column_attr in sa_inspect(type(obj)).column_attrs:
            if column_attr.key not in ("id", "scenario_id"):
                setattr(obj_copy, column_attr.key, getattr(obj, column_attr.key))
        obj_copy.scenario = scenario
        session.add(obj_copy)
        return obj_copy

    def clone(self, session: Session) -> "Scenario":
        """
        Creates a copy of the scenario, including all owned objects.
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

        # All ONETOMANY relationships on Scenario that point to owned (non-self-referential) entities.
        owned_relationships = [
            owned_relationship
            for owned_relationship in sa_inspect(Scenario).relationships
            if owned_relationship.direction.name == "ONETOMANY"
            and owned_relationship.mapper.class_ is not Scenario
            and not owned_relationship.viewonly
        ]

        # Phase 1: copy every owned object.
        # id_maps[relationship_key] = {original_id: copied_object}
        id_maps: Dict[str, Dict[int, Any]] = {}
        with session.no_autoflush:
            for owned_relationship in owned_relationships:
                id_map: Dict[int, Any] = {}
                for obj in getattr(self, owned_relationship.key):
                    obj_copy = self._copy_object(obj, session, scenario_copy)
                    id_map[obj.id] = obj_copy
                id_maps[owned_relationship.key] = id_map

        # Assign new IDs to all pending copies.
        session.flush()

        # Build table-name → id_map lookup for the FK fixup pass.
        table_to_id_map: Dict[str, Dict[int, Any]] = {
            owned_relationship.mapper.local_table.name: id_maps[owned_relationship.key]  # type: ignore[attr-defined]
            for owned_relationship in owned_relationships
        }

        # Phase 2: rewrite every FK column on every copied object so that it points
        # to the new copy rather than the original.  Autoflush is suppressed so that
        # partially-updated objects are never sent to the DB mid-pass.
        with session.no_autoflush:
            for owned_relationship in owned_relationships:
                for copied_obj in getattr(scenario_copy, owned_relationship.key):
                    for column_attr in owned_relationship.mapper.column_attrs:
                        if column_attr.key in ("id", "scenario_id"):
                            continue
                        for column in column_attr.columns:
                            for foreign_key in column.foreign_keys:
                                target_table = foreign_key.column.table.name
                                if target_table in table_to_id_map:
                                    original_val = getattr(copied_obj, column_attr.key)
                                    if original_val is not None:
                                        setattr(
                                            copied_obj,
                                            column_attr.key,
                                            table_to_id_map[target_table][
                                                original_val
                                            ].id,
                                        )

            # Manual: pure junction tables have no scenario_id and are not reachable
            # via the generic loop above; their rows must be queried and re-created.

            # VehicleType <-> VehicleClass
            vt_id_map = id_maps["vehicle_types"]
            vc_id_map = id_maps["vehicle_classes"]
            for entry_vt_vc in session.query(AssocVehicleTypeVehicleClass):
                if (
                    entry_vt_vc.vehicle_type_id in vt_id_map
                    and entry_vt_vc.vehicle_class_id in vc_id_map
                ):
                    session.add(
                        AssocVehicleTypeVehicleClass(
                            vehicle_type_id=vt_id_map[entry_vt_vc.vehicle_type_id].id,
                            vehicle_class_id=vc_id_map[entry_vt_vc.vehicle_class_id].id,
                        )
                    )
                elif (
                    entry_vt_vc.vehicle_type_id not in vt_id_map
                    and entry_vt_vc.vehicle_class_id not in vc_id_map
                ):
                    pass
                else:
                    raise ValueError(
                        "There exists an association between a vehicle type and a vehicle class"
                        " that is not in the scenario."
                    )

            # Area <-> Process
            area_id_map = id_maps["areas"]
            process_id_map = id_maps["processes"]
            for entry_area_process in session.query(AssocAreaProcess):
                if (
                    entry_area_process.area_id in area_id_map
                    and entry_area_process.process_id in process_id_map
                ):
                    session.add(
                        AssocAreaProcess(
                            area_id=area_id_map[entry_area_process.area_id].id,
                            process_id=process_id_map[entry_area_process.process_id].id,
                        )
                    )
                elif (
                    entry_area_process.area_id not in area_id_map
                    and entry_area_process.process_id not in process_id_map
                ):
                    pass
                else:
                    raise ValueError(
                        "There exists an association between an area and a process"
                        " that is not in the scenario."
                    )

        session.flush()

        # Several before_update event listeners access relationship collections during
        # the flush.  If the collection's FK fixup and the parent object's FK fixup land
        # in the same flush, the listener may lazy-load the collection before its FK
        # updates are committed, caching a stale empty list.  Expire the affected
        # attributes so the correct objects are loaded on first access by the caller.
        #
        # Rotation.before_update  → accesses rotation.trips
        #   (Trip.rotation_id updated in same flush)
        # Trip.before_update      → accesses trip.stop_times
        #   (StopTime.trip_id updated in same flush)
        # VehicleType.before_update → accesses vehicle_type.vehicle_classes
        #   (AssocVehicleTypeVehicleClass rows added in same flush)
        # Route.before_update     → accesses route.assoc_route_stations
        #   (AssocRouteStation.route_id updated in same flush)
        for rotation in scenario_copy.rotations:
            session.expire(rotation, ["trips"])
        for trip in scenario_copy.trips:
            session.expire(trip, ["stop_times"])
        for vehicle_type in scenario_copy.vehicle_types:
            session.expire(vehicle_type, ["vehicle_classes"])
        for route in scenario_copy.routes:
            session.expire(route, ["assoc_route_stations"])

        return scenario_copy

    def select_rotations(
        self, session: Session, start_time: datetime, time_window: timedelta
    ) -> None:
        """
        Keeps only the rotations that are within the time window. Deletes all other rotations from the database. This
        method is useful if (for example) your import gave you a six-month schedule, but you only want to simulate a
        week of it.

        :param session: An SQLAlchemy session to a database with eflips-model tables.
        :param start_time: The start time of the time window. Rotations that start before this time are not selected.
                           This time must have a timezone.
        :param time_window: The time window. Rotations that end after this time are not selected.
        :return: None
        """

        rotations = self.rotations

        if start_time.tzinfo is None or start_time.tzinfo.utcoffset(start_time) is None:
            raise ValueError("start_time must have a timezone")

        for rotation in rotations:
            trips = rotation.trips
            trips.sort(key=lambda x: x.departure_time)

            if (
                trips[0].departure_time < start_time
                or trips[-1].departure_time >= start_time + time_window
            ):
                for trip in trips:
                    for stop_time in trip.stop_times:
                        session.delete(stop_time)
                    session.delete(trip)

                session.delete(rotation)
        session.flush()

    def __repr__(self) -> str:
        return f"<Scenario(id={self.id}, name={self.name})>"


class EnergySource(PyEnum):
    """The kind of energy a vehicle uses for propulsion."""

    BATTERY_ELECTRIC = auto()
    DIESEL = auto()
    HYDROGEN = auto()


class VehicleType(Base):
    """
    This class represents a vehicle type, containing the technical parameters shared by all vehicles of this type.
    It is used by vehicles (which are of a specific type) and by the rotations (which are for specific vehicle types).
    """

    __tablename__ = "VehicleType"
    _table_args_list = []

    id: Mapped[int] = mapped_column(
        BigInteger().with_variant(Integer, "sqlite"), primary_key=True
    )
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

    energy_source: Mapped[EnergySource] = mapped_column(
        SqlEnum(EnergySource, native_enum=False),
        nullable=False,
        default=EnergySource.BATTERY_ELECTRIC,
    )
    """The energy/propulsion source of the vehicle type."""

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
        postgresql.ARRAY(Float, dimensions=2).with_variant(JSON(), "sqlite")
    )
    """
    The charging curve of the vehicle type. This is a 2D array of floats with two rows. The first row contains
    the state of charge, ranging from 0 (or some negative value if there is a nonzero reserve) to 1. The second row
    contains the charging power in kW. The charging curve is used to calculate the charging power of a vehicle
    using linear interpolation. The charging curve must be monotonically increasing in the first row.
    """

    v2g_curve: Mapped[List[List[float]]] = mapped_column(
        postgresql.ARRAY(Float, dimensions=2).with_variant(JSON(), "sqlite"),
        nullable=True,
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

    allowed_mass: Mapped[float] = mapped_column(Float, nullable=True)
    """The allowed payload mass of the vehicle in kg. The total mass of the vehicle is empty_mass + allowed_mass."""
    allowed_mass_constraint = CheckConstraint("allowed_mass > 0")
    _table_args_list.append(allowed_mass_constraint)

    tco_parameters: Mapped[Dict[str, Any]] = mapped_column(
        postgresql.JSONB().with_variant(JSON, "sqlite"),  # type: ignore
        nullable=True,
        server_default="""
        {
            "useful_life": 14,
            "procurement_cost": null,
            "cost_escalation": 0.02,
            "average_electricity_consumption": 1.5
        }
        """,
    )
    """The TCO (Total Cost of Ownership) parameters of the vehicle type.

    This parameter stores a JSON object containing the following fields:
    - "useful_life": The expected operational lifetime of the vehicle in years
    - "procurement_cost": The initial purchase cost per vehicle
    - "cost_escalation": Annual cost escalation factor as a decimal between 0 and 1 (e.g., 0.02 represents 2% annual cost increase)
    - "average_electricity_consumption": energy consumption in kWh/km VehicleType has energy_source BATTERY_ELECTRIC. 
    If energy_source is DIESEL, average_diesel_consumption in l/km is to be filled in.
    """

    lca_parameters: Mapped[Dict[str, Any]] = mapped_column(
        postgresql.JSONB().with_variant(JSON, "sqlite"),  # type: ignore
        nullable=True,
        server_default="""
        {
            "chassis_emission_factors_per_kg": {
                "gwp": 7.1450240595,
                "pm": 0.0130150898,
                "pocp": 0.0165275622,
                "ap": 0.0241323025,
                "ep_freshwater": 0.0032166873,
                "ep_marine": 0.0002458706,
                "fuel": 1.8687034456,
                "water": 0.0416410873
            },
            "motor_rated_power_kw": 200.0,
            "motor_emission_factors_per_kg": {
                "gwp": 10.4222178848,
                "pm": 0.0396204048,
                "pocp": 0.0369665863,
                "ap": 0.1049725031,
                "ep_freshwater": 0.0078134135,
                "ep_marine": 0.0003415405,
                "fuel": 2.5539152597,
                "water": 0.0632562358
            },
            "motor_power_to_weight_ratio": 1.5,
            "motor_emission_factors_per_unit": null,
            "motor_mass_kg": null,
            "vehicle_lifetime_years": 12.0,
            "efficiency_mv_to_lv": 0.99,
            "efficiency_lv_ac_to_dc": 0.95,
            "electricity_emission_factors_per_kwh": {
                "gwp": 0.4197609117257143,
                "pm": 1.465410857142857e-05,
                "pocp": 0.000604223382857143,
                "ap": 0.00038782769142857145,
                "ep_freshwater": 0.0007912056857142857,
                "ep_marine": 4.684067999999999e-05,
                "fuel": 0.09882671976,
                "water": 0.0026895370114285713
            },
            "diesel_emission_factors_per_kg": null,
            "average_consumption_kwh_per_km": 1.5,
            "diesel_consumption_kg_per_km": null,
            "maintenance_per_year": {
                "BATTERY_ELECTRIC": {
                    "gwp": 2557.781999876,
                    "pm": 1.5140544646,
                    "pocp": 3.7768838271,
                    "ap": 4.6374171771,
                    "ep_freshwater": 1.9245437185,
                    "ep_marine": 0.351172717,
                    "fuel": 766.0160472554,
                    "water": 17.4877028381
                }
              }
            }        
            """,
    )
    """LCA (Life Cycle Assessment) parameters for this vehicle type.

    Stored as a JSON object. Use ``eflips.lca.VehicleTypeLcaParams.from_dict()``
    to deserialise and ``.to_dict()`` to serialise. Contains chassis, motor,
    use-phase, and maintenance emission factors.

    See the eflips-lca design document for the full schema.
    """

    consumption: Mapped[float] = mapped_column(Float, nullable=True)
    """
    The vehicle's energy consumption in kWh/km. This is used to calculate the energy consumption of a trip. Can
    be None if we are using more detailed consumption models.
    
    Either this or consumption_lut must be specified. Both cannot exist at the same time.
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

    assoc_vehicle_type_vehicle_classes: Mapped[
        "AssocVehicleTypeVehicleClass"
    ] = relationship("AssocVehicleTypeVehicleClass", viewonly=True)

    __table_args__ = tuple(_table_args_list)

    def __repr__(self) -> str:
        return f"<VehicleType(id={self.id}, name={self.name})>"


@event.listens_for(VehicleType, "before_insert")
@event.listens_for(VehicleType, "before_update")
def check_vehicle_type_before_commit(_: Any, __: Any, target: VehicleType) -> None:
    """
    A VehicleType may hav consumption xor consumption_lut, but not both.

    :param target: A VehicleType object
    :return: Nothing. Raises an exception if something is wrong.
    """

    number_of_consumption_luts = 0
    for vehicle_class in target.vehicle_classes:
        if vehicle_class.consumption_lut is not None:
            number_of_consumption_luts += 1

    if number_of_consumption_luts > 1:
        warnings.warn(
            "A VehicleType may at most have one consumption_lut.",
            ConsistencyWarning,
        )
    elif number_of_consumption_luts == 1 and target.consumption is not None:
        warnings.warn(
            "A VehicleType may have consumption xor consumption_lut, but not both.",
            ConsistencyWarning,
        )
    elif number_of_consumption_luts == 0 and target.consumption is None:
        warnings.warn(
            "A VehicleType must have either consumption or consumption_lut.",
            ConsistencyWarning,
        )
    else:
        pass  # Everything is fine


class BatteryType(Base):
    __tablename__ = "BatteryType"

    id: Mapped[int] = mapped_column(
        BigInteger().with_variant(Integer, "sqlite"), primary_key=True
    )
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

    chemistry: Mapped[str] = mapped_column(Text)
    """The chemistry of the battery as a plain string, e.g. ``'LFP'`` or ``'NMC622'``."""

    tco_parameters: Mapped[Dict[str, Any]] = mapped_column(
        postgresql.JSONB().with_variant(JSON, "sqlite"),  # type: ignore
        nullable=True,
        server_default="""
        {
            "useful_life":7,
            "procurement_cost": null,
            "cost_escalation": 0.01
        }
        """,
    )
    """
    The Total Cost of Ownership (TCO) parameters for the battery type.
    
    Stored as a JSON object containing the following fields:
    
    - useful_life (int): The expected operational lifespan of the battery in years.
      Represents how long the battery is expected to maintain acceptable 
      performance before requiring replacement.
    
    - procurement_cost (float or null): The initial acquisition cost per kWh 
      of battery capacity.
    
    - cost_escalation (float): The annual rate of cost change as a decimal
      between 0 and 1. Negative values indicate cost reductions over time,
      while positive values indicate cost increases. For example, -0.03
      represents a 3% annual cost reduction.
    """

    lca_parameters: Mapped[Dict[str, Any]] = mapped_column(
        postgresql.JSONB().with_variant(JSON, "sqlite"),  # type: ignore
        nullable=True,
        server_default="""
        {
            "emission_factors_per_kg": 
            {
                "gwp": 14.7545001202,
                "pm": -0.0183173103,
                "pocp": 0.0485464758,
                "ap": -0.05589953259999997,
                "ep_freshwater": 0.0067215502,
                "ep_marine": 0.0007635275,
                "fuel": 4.1624314205,
                "water": 0.0873524419
            },
            "battery_lifetime_years": 8.0
            }
        """,
    )
    """LCA parameters for this battery type.

    Stored as a JSON object. Use ``eflips.lca.BatteryTypeLcaParams.from_dict()``
    to deserialise. Contains emission factors per kg and battery lifetime.
    """

    def __repr__(self) -> str:
        return f"<BatteryType (id={self.id}, specific_mass={self.specific_mass}, chemistry={self.chemistry})>"


class Vehicle(Base):
    """
    A vehicle is a concrete vehicle of a certain type.
    """

    __tablename__ = "Vehicle"

    id: Mapped[int] = mapped_column(
        BigInteger().with_variant(Integer, "sqlite"), primary_key=True
    )
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

    def __repr__(self) -> str:
        return f"<Vehicle(id={self.id}, name={self.name})>"


class VehicleClass(Base):
    """
    VehicleClasses allow a many-to-many relationship between vehicles and classes, which may be used for specifying
    things such as "any 12m bus" or "any 18m bus".

    The VehicleClass table is not used directly, but through the association table AssocVehicleTypeVehicleClass.

    **Support is currently incomplete. THis only exists as a stub (and is used by eflip-LCA), but is not implemented
    in django.simba or eflips-depot**
    """

    __tablename__ = "VehicleClass"

    id: Mapped[int] = mapped_column(
        BigInteger().with_variant(Integer, "sqlite"), primary_key=True
    )
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

    consumption_lut: Mapped["ConsumptionLut"] = relationship(
        "ConsumptionLut", back_populates="vehicle_class"
    )
    """
    A consumption look up table.

    Either this or consumption must be specified. Both cannot exist at the same time.
    """

    assoc_vehicle_type_vehicle_classes: Mapped[
        "AssocVehicleTypeVehicleClass"
    ] = relationship("AssocVehicleTypeVehicleClass", viewonly=True)

    def __repr__(self) -> str:
        return f"<VehicleClass(id={self.id}, name={self.name})>"


class AssocVehicleTypeVehicleClass(Base):
    """
    The association table for the many-to-many relationship between vehicles and classes.
    """

    __tablename__ = "AssocVehicleTypeVehicleClass"
    id: Mapped[int] = mapped_column(
        BigInteger().with_variant(Integer, "sqlite"), primary_key=True
    )
    """Not the primary key and not used in SQLAlchemy, but required by Django."""

    vehicle_type_id: Mapped[int] = mapped_column(ForeignKey("VehicleType.id"))
    """The unique identifier of the vehicle type. Foreign key to :attr:`VehicleType.id`."""
    vehicle_type: Mapped[VehicleType] = relationship(
        "VehicleType", overlaps="vehicle_classes,vehicle_types"
    )

    vehicle_class_id: Mapped[int] = mapped_column(ForeignKey("VehicleClass.id"))
    """The unique identifier of the vehicle class. Foreign key to :attr:`VehicleClass.id`."""
    vehicle_class: Mapped[VehicleClass] = relationship(
        "VehicleClass", overlaps="vehicle_classes,vehicle_types"
    )

    def __repr__(self) -> str:
        return f"<AssocVehicleTypeVehicleClass(id={self.id}, vehicle_type_id={self.vehicle_type_id}, vehicle_class_id={self.vehicle_class_id})>"


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

    STANDBY = auto()
    """Standing in the depot while waiting for something. Not yet ready for departure."""

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

    id: Mapped[int] = mapped_column(
        BigInteger().with_variant(Integer, "sqlite"), primary_key=True
    )
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

    vehicle_id: Mapped[int] = mapped_column(
        ForeignKey("Vehicle.id"), nullable=True, index=True
    )
    """The unique identifier of the vehicle. Foreign key to :attr:`Vehicle.id`."""
    vehicle: Mapped["Vehicle"] = relationship("Vehicle", back_populates="events")
    """The vehicle."""

    station_id: Mapped[int] = mapped_column(
        ForeignKey("Station.id"), nullable=True, index=True
    )
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

    trip_id: Mapped[int] = mapped_column(
        ForeignKey("Trip.id"), nullable=True, index=True
    )
    """The unique identifier of the trip. Foreign key to :attr:`Trip.id`."""
    trip: Mapped["Trip"] = relationship("Trip", back_populates="events")

    time_start: Mapped[datetime] = mapped_column(
        DateTime(timezone=True).with_variant(TimeStampWithTz, "sqlite"),
        nullable=False,
        index=False,
    )
    """The time the event starts."""

    time_end: Mapped[datetime] = mapped_column(
        DateTime(timezone=True).with_variant(TimeStampWithTz, "sqlite"), nullable=False
    )
    """The time the event ends."""

    soc_start: Mapped[float] = mapped_column(Float, nullable=False)
    """
    The state of charge at the start of the event. This should refer to the net battery capacity.
    """

    soc_end: Mapped[float] = mapped_column(Float, nullable=False)
    """The state of charge at the end of the event. This should refer to the net battery capacity."""

    event_type: Mapped[EventType] = mapped_column(
        SqlEnum(EventType, native_enum=False), nullable=False
    )
    """The type of the event."""

    description: Mapped[str] = mapped_column(Text, nullable=True)
    """A description of the event. Used to display additional information to the user."""

    timeseries: Mapped[Dict[str, List[Union[datetime, str, float]]]] = mapped_column(
        postgresql.JSONB().with_variant(JSON, "sqlite"), nullable=True  # type: ignore
    )
    """
    Dict with mandatory keys „time“ (ISO 18601 with TZ), „soc“ (0-1) and optional keys „distance“ (m, along route for 
    trip) + other freely defined keys. Array of same length for each key
    """

    __table_args__ = (
        CheckConstraint("soc_start <= 1"),
        CheckConstraint("soc_end <= 1"),
        # Also make sure the event type is valid for the nullable fields
        CheckConstraint(
            "(station_id IS NOT NULL AND event_type IN ('CHARGING_OPPORTUNITY', 'STANDBY_DEPARTURE', 'STANDBY'))  OR "
            "(area_id IS NOT NULL AND subloc_no IS NOT NULL AND station_id IS NOT NULL AND event_type IN ('CHARGING_DEPOT', 'SERVICE', "
            "'STANDBY_DEPARTURE', 'STANDBY', 'PRECONDITIONING')) OR"
            "(trip_id IS NOT NULL AND subloc_no IS NULL AND event_type IN ('DRIVING'))",
            name="filled_fields_type_combination",
        ),
        CheckConstraint("time_start < time_end", name="duration_positive"),
        Index(
            "idx_station_event_time_range",
            station_id,
            event_type,
            time_start,
            time_end,
        ),
    )

    def __repr__(self) -> str:
        return f"<Event(id={self.id}, event_type={self.event_type}, time_start={self.time_start}, time_end={self.time_end})>"


# Add PostgreSQL-specific constraint using DDL event
postgresql_exclude = DDL(
    f"""
    ALTER TABLE "{Event.__tablename__}" ADD CONSTRAINT scenario_id_time_range_excl 
    EXCLUDE USING gist (
        scenario_id WITH =,
        vehicle_id WITH =,
        tstzrange(time_start, time_end, '()') WITH &&
    )
"""
)  # type: ignore

event.listen(
    Event.__table__, "after_create", postgresql_exclude.execute_if(dialect="postgresql")
)


@event.listens_for(Event, "before_insert")
@event.listens_for(Event, "before_update")
def check_event_before_commit(_: Any, __: Any, target: Event) -> None:
    """
    1. If the event has a timeseries, check if the keys are correct. Also make sure the first timestamp is >= time_start
    and the last timestamp is <= time_end.

    2. Check if the start or end time is not a full second, warn the user if it is not.

    :param target: an event object
    :return: Nothing. Raises an exception if something is wrong.
    """
    # Check if the timeseries keys are correct
    if target.timeseries is not None:
        if "time" not in target.timeseries:
            raise ValueError("The timeseries must have a 'time' key.")
        else:
            # Each entry must either be a string
            for time in target.timeseries["time"]:
                if not isinstance(time, str):
                    raise ValueError(
                        "The 'time' key must contain strings or datetime objects."
                    )
            # The first timestamp must be >= time_start and the last timestamp must be <= time_end
            first_timestamp = datetime.fromisoformat(target.timeseries["time"][0])  # type: ignore
            if first_timestamp < target.time_start:
                raise ValueError(
                    "The first timestamp in the timeseries must be >= time_start."
                )

            last_timestamp = datetime.fromisoformat(target.timeseries["time"][-1])  # type: ignore
            if last_timestamp > target.time_end:
                raise ValueError(
                    "The last timestamp in the timeseries must be <= time_end."
                )

        if "soc" not in target.timeseries:
            raise ValueError("The timeseries must have a 'soc' key.")

    # Check if the arrival or departure time is not a full second
    if target.time_start.microsecond != 0:
        warnings.warn(
            "The departure time of a trip should be a full second. "
            f"Trip {target.id} violates this.",
            ConsistencyWarning,
        )
    if target.time_end.microsecond != 0:
        warnings.warn(
            "The arrival time of a trip should be a full second. "
            f"Trip {target.id} violates this.",
            ConsistencyWarning,
        )


class ConsumptionLut(Base):
    """
    The Consumption table stores the energy consumption look-up-tables for each vehicle class.

    Uses a regression model generated from real world electric bus data to create a consumption table in
    django-simba format (temperature, speed, level of loading, incline, consumption) and exports it into
    the session database.
    """

    __tablename__ = "ConsumptionLut"
    __table_args__ = (
        UniqueConstraint("scenario_id", "vehicle_class_id"),
        UniqueConstraint("scenario_id", "name"),
    )

    id: Mapped[int] = mapped_column(
        BigInteger().with_variant(Integer, "sqlite"), primary_key=True
    )
    """The unique identifier of the consumption. Auto-incremented."""

    scenario_id: Mapped[int] = mapped_column(ForeignKey("Scenario.id"), nullable=False)
    """The unique identifier of the scenario. Foreign key to :attr:`Scenario.id`."""
    scenario: Mapped[Scenario] = relationship(
        "Scenario", back_populates="consumption_luts"
    )
    """The scenario."""

    name = mapped_column(Text, nullable=False)  # Because django-simba requires a name
    """A name for the consumption table."""

    vehicle_class_id: Mapped[int] = mapped_column(
        ForeignKey("VehicleClass.id"), nullable=False
    )
    """The unique identifier of the vehicle type. Foreign key to :attr:`VehicleClass.id`."""

    vehicle_class: Mapped[VehicleClass] = relationship(
        "VehicleClass", back_populates="consumption_lut"
    )
    """The vehicle class."""

    columns = mapped_column(
        postgresql.JSONB().with_variant(JSON, "sqlite"), nullable=False  # type: ignore
    )
    """
    A JSON-encoded list of column name strings. The order of these should match the order of the values for each row
    in the data_points
    """

    data_points: Mapped[List[List[float]]] = mapped_column(
        postgresql.ARRAY(Float, dimensions=2).with_variant(JSON(), "sqlite"),
        nullable=False,
    )
    """
    A list of data points. These are the coordinates of the data point. Its value is stored in the `value` column.
    The order of columns is the entry in the `columns` column.
    """

    values: Mapped[List[float]] = mapped_column(
        postgresql.ARRAY(Float, dimensions=1).with_variant(JSON(), "sqlite"),
        nullable=False,
    )
    """
    A list of consumption values in kWh/km. The corresponding temperatures, inclines etc. are stored in the 
    `data_points` column.
    """

    # String Lookups expected in the Dataframes containing Consumption data
    INCLINE = "incline"
    T_AMB = "t_amb"
    LEVEL_OF_LOADING = "level_of_loading"
    SPEED = "mean_speed_kmh"
    CONSUMPTION = "consumption_kwh_per_km"

    @staticmethod
    def calc_consumption(
        trip_distance: float,
        temperature: float,
        mass: float,
        duration: float,
        incline: float = 0.0,
    ) -> float:
        """
        This function calculates the consumption of the trip according to the model of
        Ji, Bie, Zeng, Wang https://doi.org/10.1016/j.commtr.2022.100069, augmented
        with a linear physics-based slope term (the original Ji model has none).
        :param trip_distance: Travelled distance in km
        :param temperature: Average temperature during trip in degrees Celsius
        :param mass: Curb weight + passengers in kg
        :param duration: Trip time in minutes
        :param incline: Average road grade as a fraction (e.g. 0.05 = +5 % uphill, -0.03 = -3 % downhill). Defaults to 0 (level road).
        :return: Trip energy in kWh
        """

        # Calculate trip energy for traction and BTMS w1
        term = (
            -8.091
            + 0.533 * np.log(trip_distance)
            + 0.78 * np.log(mass)
            + 0.353 * np.log(duration)
            + 0.008 * np.abs(temperature - 23.7)
        )
        w1: float = np.exp(term)

        # Calculate trip energy for AC w2
        # Possible enhancment: Derive a formula for how t_AC_percent is changing over temperature
        ks = [0.053, 0.11]  # Factor for cooling / heating
        AC_threshold = 20  # Above this temperature: cooling, below: heating
        t_AC_percent = (
            1  # Percentage of how long of the trip heating/cooling is turned ON
        )
        if temperature >= AC_threshold:
            k = ks[0]
        else:
            k = ks[1]
        w2 = k * t_AC_percent * duration

        # Slope contribution: m * g * sin(theta) per metre of travel.
        # Small-angle: sin(theta) ≈ incline. Distance is in km, so multiply by
        # 1000 m/km, then convert J → kWh by dividing by 3.6e6, giving / 3600.
        gravity = 9.81  # m/s^2
        w_slope: float = mass * gravity * incline * trip_distance / 3600.0  # kWh

        # Total trip energy
        # Possible Enhancement: Check why model energy is this low
        correction = 1.0  # Energy seems a bit low compared to other data
        trip_energy = correction * (w1 + w2 + w_slope)
        trip_consumption = trip_energy / trip_distance

        return trip_consumption

    @staticmethod
    def table_generator(vehicle_type: VehicleType) -> pd.DataFrame:
        """
        Takes VehicleType information to create a consumption table in django-simba format.
        :return:
        """
        if vehicle_type.empty_mass is None:
            raise ValueError("Vehicle type has no empty mass.")
        minimum_mass = vehicle_type.empty_mass
        if vehicle_type.allowed_mass is None:
            raise ValueError("Vehicle type has no allowed mass.")
        maximum_mass = vehicle_type.allowed_mass

        mass_range = [minimum_mass, maximum_mass]  # kg
        mass_steps = 11
        masses = np.linspace(mass_range[0], mass_range[1], mass_steps, endpoint=True)
        delta_mass = mass_range[1] - mass_range[0]
        level_of_loading = (masses - mass_range[0]) / delta_mass

        # Temperatures
        temperature_range = [-20, 40]  # °C
        temperature_steps = 11
        temperatures = np.linspace(
            temperature_range[0], temperature_range[1], temperature_steps, endpoint=True
        )

        # Speeds
        distance = 10  # fixed value for duration calculation
        speed_range = [5, 60]  # km/h
        speed_steps = 11
        speeds = np.linspace(speed_range[0], speed_range[1], speed_steps, endpoint=True)

        # Inclines (fraction of rise / run, e.g. 0.05 = +5 %)
        incline_range = [-0.10, 0.10]
        incline_steps = 5
        inclines = np.linspace(
            incline_range[0], incline_range[1], incline_steps, endpoint=True
        )

        # Calculate consumption
        combinations = list(product(temperatures, speeds, level_of_loading, inclines))

        consumption_list = []
        for combo in combinations:
            temp, speed, lol, inc = combo
            duration = distance / speed * 60
            mass = (lol + 1) * delta_mass
            consumption = ConsumptionLut.calc_consumption(
                distance, temp, mass, duration, inc  # type: ignore
            )
            consumption_list.append(consumption)

        # Create table and return
        consumption_table = pd.DataFrame(
            combinations,
            columns=[
                ConsumptionLut.T_AMB,
                ConsumptionLut.SPEED,
                ConsumptionLut.LEVEL_OF_LOADING,
                ConsumptionLut.INCLINE,
            ],
        )
        consumption_table[ConsumptionLut.CONSUMPTION] = consumption_list

        return consumption_table

    @staticmethod
    def df_to_consumption_obj(
        df: pd.DataFrame,
        scenario_or_id: Union[Scenario, int],
        vehicle_class_or_id: Union[VehicleClass, int],
    ) -> "ConsumptionLut":
        # Expand the scenario to an int and a Scenario object
        if isinstance(scenario_or_id, Scenario):
            scenario = scenario_or_id
            scenario_id = scenario.id
        elif isinstance(scenario_or_id, int):
            scenario_id = scenario_or_id
            scenario = None
        else:
            raise ValueError(
                "scenario_or_id must be either a Scenario object or an int."
            )

        # Expand the VehicleType to an int and a VehicleType object
        if isinstance(vehicle_class_or_id, VehicleClass):
            vehicle_class = vehicle_class_or_id
            vehicle_class_id = vehicle_class.id
        elif isinstance(vehicle_class_or_id, int):
            vehicle_class_id = vehicle_class_or_id
            vehicle_class = None
        else:
            raise ValueError(
                "vehicle_type_or_id must be either a VehicleType object or an int."
            )

        columns = [
            ConsumptionLut.INCLINE,
            ConsumptionLut.T_AMB,
            ConsumptionLut.LEVEL_OF_LOADING,
            ConsumptionLut.SPEED,
        ]
        data_points = np.array(df.loc[:, columns].values).tolist()
        values = np.array(df.loc[:, ConsumptionLut.CONSUMPTION].values).tolist()
        # Only pass the relationship when it is not None — otherwise SQLAlchemy
        # writes the None through to the FK column on flush and overwrites the
        # scenario_id / vehicle_class_id we just set.
        kwargs = dict(
            name=f"Empirical consumption for {vehicle_class.name if vehicle_class else vehicle_class_id}",
            scenario_id=scenario_id,
            vehicle_class_id=vehicle_class_id,
            columns=columns,
            data_points=data_points,
            values=values,
        )
        if scenario is not None:
            kwargs["scenario"] = scenario
        if vehicle_class is not None:
            kwargs["vehicle_class"] = vehicle_class
        return ConsumptionLut(**kwargs)

    @classmethod
    def from_vehicle_type(
        cls, vehicle_type: VehicleType, vehicle_class: VehicleClass
    ) -> "ConsumptionLut":
        df = cls.table_generator(vehicle_type)
        return cls.df_to_consumption_obj(df, vehicle_type.scenario, vehicle_class)


class Temperatures(Base):
    """
    The Consumption table stores the energy consumption look-up-tables for each vehicle class.

    Uses a regression model generated from real world electric bus data to create a consumption table in
    django-simba format (temperature, speed, level of loading, incline, consumption) and exports it into
    the session database.
    """

    __tablename__ = "Temperatures"
    __table_args__ = (
        UniqueConstraint("scenario_id", "id"),  # This works in both databases
    )

    id: Mapped[int] = mapped_column(
        BigInteger().with_variant(Integer, "sqlite"), primary_key=True
    )
    """The unique identifier of the consumption. Auto-incremented."""

    scenario_id: Mapped[int] = mapped_column(ForeignKey("Scenario.id"), nullable=False)
    """The unique identifier of the scenario. Foreign key to :attr:`Scenario.id`."""
    scenario: Mapped[Scenario] = relationship("Scenario", back_populates="temperatures")
    """The scenario."""

    name: Mapped[str] = mapped_column(Text, nullable=False)
    """A name for the temperature table."""

    use_only_time: Mapped[bool] = mapped_column(Boolean, nullable=False, default=True)
    """
    Whether the temperature data is for one repeating day. If False, the temperature data is for multiple days.
    If true, it is for one day and all other days should use the values from this day.
    """

    datetimes: Mapped[List[datetime]] = mapped_column(
        postgresql.ARRAY(DateTime(timezone=True)).with_variant(PickleType(), "sqlite")
    )
    """
    The datetimes of the temperature data. If is_one_repeating_day is True, this should be a single day.
    The length of this list should be the same as the length of the temperatures.
    """

    data: Mapped[List[float]] = mapped_column(
        postgresql.ARRAY(Float).with_variant(JSON(), "sqlite")
    )
    """
    The temperatures in degrees Celsius. The order of the temperatures should match the order of the datetimes.
    The length of this list should be the same as the length of the datetimes.
    """


# Add PostgreSQL-specific array check constraint using DDL event
postgresql_array_check = DDL(
    f"""
    ALTER TABLE "{Temperatures.__tablename__}" ADD CONSTRAINT equal_array_lengths 
    CHECK (array_length(datetimes, 1) = array_length(data, 1))
"""
)  # type: ignore

event.listen(
    Temperatures.__table__,
    "after_create",
    postgresql_array_check.execute_if(dialect="postgresql"),
)


class ChargingPointType(Base):

    """
    This class is designed for distinguishing between charging point at area or at station.
    """

    __tablename__ = "ChargingPointType"

    id: Mapped[int] = mapped_column(
        BigInteger().with_variant(Integer, "sqlite"), primary_key=True
    )
    """The unique identifier of the charging point type. Auto-incremented."""

    scenario_id: Mapped[int] = mapped_column(ForeignKey("Scenario.id"), nullable=False)
    """The unique identifier of the scenario. Foreign key to :attr:`Scenario.id`."""
    scenario: Mapped["Scenario"] = relationship(
        "Scenario", back_populates="charging_point_types"
    )
    """The scenario."""

    name: Mapped[str] = mapped_column(Text, nullable=False)
    """The name of the charging point type. """
    name_short: Mapped[str] = mapped_column(Text, nullable=True)
    """The short name of the charging point type (if available)."""

    tco_parameters: Mapped[Dict[str, Any]] = mapped_column(
        postgresql.JSONB().with_variant(JSON, "sqlite"),  # type: ignore
        nullable=True,
        server_default="""
        {
            "useful_life":20,
            "procurement_cost": null,
            "cost_escalation":0.02
        }
        """,
    )
    """The TCO (Total Cost of Ownership) parameters of the charging point.

    Stored as a JSON object containing the following fields:

    - useful_life (int): Expected operational lifespan of the charging point in years.
      Default: 20 years

    - procurement_cost (float, optional): Initial purchase cost per charging point.

    - cost_escalation (float): Annual cost escalation rate as a decimal.
      Should be between 0.0 and 1.0 (e.g., 0.02 = 2% annual increase).
      Used to project future operational costs over the useful life period.
    """

    lca_parameters: Mapped[Dict[str, Any]] = mapped_column(
        postgresql.JSONB().with_variant(JSON, "sqlite"),  # type: ignore
        nullable=True,
        server_default="""
            {
              "control_unit_emissions": {
                "gwp": 650.2638448711001,
                "pm": 14.284577223300001,
                "pocp": 7.161514969900001,
                "ap": 49.9366794504,
                "ep_freshwater": -1.3148274563,
                "ep_marine": -0.038361769399999995,
                "fuel": 198.08683628949998,
                "water": 0.16472508080000026
              },
              "power_unit_emission": {
                "gwp": 4517.1716509588005,
                "pm": 73.75310580600001,
                "pocp": 39.562258428,
                "ap": 256.6122330522,
                "ep_freshwater": -6.1600977037,
                "ep_marine": -0.1553323559,
                "fuel": 1210.095218871,
                "water": 9.0850155355
              },
              "power_unit_rated_power_kw": 350.0,
              "user_unit_emission": {
                "gwp": 528.0177374135001,
                "pm": 6.282905781799999,
                "pocp": 3.1490487038,
                "ap": 19.1536947284,
                "ep_freshwater": -0.272372094,
                "ep_marine": -0.0067322579,
                "fuel": 159.8769760205,
                "water": 1.3416479734999998
              },
              "transformer_emissions": {
                "gwp": 8100.000000000007,
                "pm": 17.27999999999999,
                "pocp": 20.48595930631943,
                "ap": 54.50000000000005,
                "ep_freshwater": 2.200000000000002,
                "ep_marine": 5.400000000000005,
                "fuel": 3200.000000000003,
                "water": 3966.81
              },
              "transformer_ref_power_kw": 315.0,
              "concrete_emissions_per_m3": {
                "gwp": 307.953,
                "pm": 0.298,
                "pocp": 1.801,
                "ap": 0.684,
                "ep_freshwater": 0.037,
                "ep_marine": 0.003,
                "fuel": 48.306,
                "water": 2.677
              },
              "foundation_volume_per_point_m3": 3.96,
              "infrastructure_lifetime_years": 20.0
            }        
        
        """,
    )
    """LCA parameters for this charging point type.

    Stored as a JSON object. Use
    ``eflips.lca.ChargingPointTypeLcaParams.from_dict()`` to deserialise.
    Contains control/power/user unit emission factors, concrete parameters,
    and infrastructure lifetime.
    """

    stations: Mapped[List["Station"]] = relationship(
        "Station",
        back_populates="charging_point_type",
    )

    """The stations that have this charging point type."""

    areas: Mapped[List["Area"]] = relationship(
        "Area",
        back_populates="charging_point_type",
    )

    """The areas that have this charging point type."""

    def __repr__(self) -> str:
        return f"<ChargingPointType(id={self.id}, name={self.name})>"
