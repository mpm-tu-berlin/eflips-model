import copy
from abc import ABCMeta
from datetime import datetime
from typing import Dict, Any, List, Tuple

import sqlalchemy.orm
from sqlalchemy import (
    Column,
    BigInteger,
    Text,
    DateTime,
    JSON,
    ForeignKey,
    Integer,
    func,
    Float,
    CheckConstraint,
    Boolean,
)
from sqlalchemy.dialects import postgresql
from sqlalchemy.orm import mapped_column, Mapped, relationship, Session, make_transient

from eflips.model import Base


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
    """The time the simulation was finished. Automatically set to the current time at simulation end. Null if not yet finished."""
    simba_options: Mapped[Dict[str, Any]] = mapped_column(
        postgresql.JSONB, nullable=True
    )
    """The options for the simBA simulation. Stored as a JSON object."""
    eflips_depot_options: Mapped[Dict[str, Any]] = mapped_column(
        postgresql.JSONB, nullable=True
    )
    """The options for the eflips-depot simulation. Stored as a JSON object."""

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

    battery_capacity_reserve: Mapped[float] = mapped_column(Float, nullable=True)
    """The battery capacity reserve below 0 kWh 'capacity' in kWh. Using this value in generating evaluation, 
    things such as "always 10% reserve" can be modeled."""
    battery_capacity_reserve_constraint = CheckConstraint(
        "battery_capacity_reserve >= 0"
    )
    _table_args_list.append(battery_capacity_reserve_constraint)

    charging_curve: Mapped[List[List[float]]] = mapped_column(
        postgresql.ARRAY(Integer, dimensions=2)
    )
    """
    The charging curve of the vehicle type. This is a 2D array of floats with two rows. The first row contains
    the state of charge, ranging from 0 (or some negative value if there is a nonzero reserve) to 1. The second row
    contains the charging power in kW. The charging curve is used to calculate the charging power of a vehicle
    using linear interpolation. The charging curve must be monotonically increasing in the first row.
    """

    v2g_curve: Mapped[List[List[float]]] = mapped_column(
        postgresql.ARRAY(Integer, dimensions=2), nullable=True
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

    opportunity_charge_capable: Mapped[bool] = mapped_column(Boolean)
    """
    Whether the bus is capable of automatic highpower charging. All buses are assumed to be capable of (depot) 
    conductive charging.
    """

    minimum_charging_power: Mapped[float] = mapped_column(Float, server_default="0.0")
    """If the charging power falls below this value, charging is canceled"""
    minimum_charging_power_constraint = CheckConstraint("minimum_charging_power >= 0")
    _table_args_list.append(minimum_charging_power_constraint)

    # Shape is a three-entry array of floats, representing the length, width, and height of the vehicle in meters.
    shape: Mapped[List[float]] = mapped_column(
        postgresql.ARRAY(Integer, dimensions=1, as_tuple=True), nullable=True
    )
    """
    The shape of the vehicle. This is a 1D array of floats with three entries, representing the length, width, and
    height of the vehicle in meters.
    """

    empty_mass: Mapped[float] = mapped_column(Float, nullable=True)
    """The empty mass of the vehicle in kg."""
    empty_mass_constraint = CheckConstraint("empty_mass > 0")
    _table_args_list.append(empty_mass_constraint)

    vehicles = relationship("Vehicle", back_populates="vehicle_type")

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
