from datetime import datetime, timedelta
from enum import auto, Enum as PyEnum
from typing import List, Tuple, TYPE_CHECKING

from sqlalchemy import (
    BigInteger,
    Boolean,
    CheckConstraint,
    Enum as SqlEnum,
    Float,
    ForeignKey,
    Integer,
    Interval,
    Text,
    UniqueConstraint,
    Constraint,
)
from sqlalchemy.dialects import postgresql
from sqlalchemy.orm import Mapped, mapped_column, relationship

from eflips.model import Base

if TYPE_CHECKING:
    from eflips.model import Scenario, VehicleType, Event, Station


class Depot(Base):
    """
    The Depot represents a palce where vehicles not engaged in a schedule are parked,
    processed and dispatched.
    """

    __tablename__ = "Depot"
    id: Mapped[int] = mapped_column(BigInteger, primary_key=True)
    """The unique idenfitier of the depot. Auto-incremented."""

    scenario_id: Mapped[int] = mapped_column(ForeignKey("Scenario.id"))
    """The unique identifier of the scenario. Foreign key to :attr:`Scenario.id`."""
    scenario: Mapped["Scenario"] = relationship("Scenario", back_populates="depots")
    """The scenario this depot belongs to."""

    name: Mapped[str] = mapped_column(Text)
    """A name for the depot."""
    name_short: Mapped[str] = mapped_column(Text, nullable=True)
    """An optional short name for the depot."""

    station_id: Mapped[int] = mapped_column(ForeignKey("Station.id"))
    """The station where the depot is located. This depot handles :attr:`Rotation` starting and ending at this station. Foreign key to :attr:`Station.id`."""
    station: Mapped["Station"] = relationship("Station", back_populates="depot")
    """The station where the depot is located. This depot handles :attr:`Rotation` starting and ending at this station."""

    default_plan_id: Mapped[int] = mapped_column(ForeignKey("Plan.id"))
    """The default plan of this depot. Foreign key to :attr:`Plan.id`."""
    default_plan: Mapped["Plan"] = relationship("Plan", back_populates="depot")

    areas: Mapped[List["Area"]] = relationship("Area", back_populates="depot")
    """The areas of this depot."""

    __table_args__ = (
        # What we actually would like is have station_id globally unique, but this raises
        # a violation during the step of copyying wheer the data is duplicated already but the relationships
        # are not yet updated. So we have to live with the unique constraint on the scenario level.
        UniqueConstraint(scenario_id, station_id),
    )

    def __repr__(self) -> str:
        return f"<Depot(id={self.id}, name={self.name})>"


class Plan(Base):
    """
    The Plan represents a certain order of processes, which are executed on vehicles in a depot.
    """

    __tablename__ = "Plan"

    id: Mapped[int] = mapped_column(BigInteger, primary_key=True)
    """The unique identifier of the plan. Auto-incremented."""

    scenario_id: Mapped[int] = mapped_column(ForeignKey("Scenario.id"))
    """The unique identifier of the scenario. Foreign key to :attr:`Scenario.id`."""
    scenario: Mapped["Scenario"] = relationship("Scenario", back_populates="plans")
    """The scenario this plan belongs to."""

    name: Mapped[str] = mapped_column(Text)
    """A name for the plan."""

    depot: Mapped["Depot"] = relationship("Depot", back_populates="default_plan")

    asssoc_plan_process: Mapped[List["AssocPlanProcess"]] = relationship(
        "AssocPlanProcess",
        back_populates="plan",
        order_by="AssocPlanProcess.ordinal",
    )
    """The association between this plan and its processes. Here, the ordinal of the process can be set."""

    processes: Mapped[List["Process"]] = relationship(
        "Process",
        secondary="AssocPlanProcess",
        back_populates="plans",
        order_by="AssocPlanProcess.ordinal",
        viewonly=True,
    )

    def __repr__(self) -> str:
        return f"<Plan(id={self.id}, name={self.name})>"


class AreaType(PyEnum):
    """This class represents the type of area in eFLIPS-Depot"""

    DIRECT_ONESIDE = auto()
    """A direct area where vehicles drive in form one side only."""

    DIRECT_TWOSIDE = auto()
    """A direct area where vehicles drive in form both sides. Also called a "herringbone" configuration."""

    LINE = auto()
    """A line area where vehicles are parked in a line. There might be one or more rows in the area."""


class Area(Base):
    """
    An Area represents a certain area in a depot, where at least one process is available.

    All slots in the area may be directly accessible, or the area may be a line area where vehicles are parked in a
    line. In such an area, only the first vehicle in the line is directly accessible, the second vehicle can only be
    removed after the first vehicle has been removed, and so on. However vehicles can only been added to the end of the
    line. So if it's filled up, *all* vehicles have to be removed to add a new one. If there's one slot left and one
    vehicle is removed, there's still only one slot left, not two.

    """

    __tablename__ = "Area"

    _table_args_list: List[Constraint] = []

    id: Mapped[int] = mapped_column(BigInteger, primary_key=True)
    """The unique identifier of the area. Auto-incremented."""

    scenario_id: Mapped[int] = mapped_column(ForeignKey("Scenario.id"))
    """The unique identifier of the scenario. Foreign key to :attr:`Scenario.id`."""
    scenario: Mapped["Scenario"] = relationship("Scenario", back_populates="areas")
    """The scenario this area belongs to."""

    depot_id: Mapped[int] = mapped_column(ForeignKey("Depot.id"))
    """The unique identifier of the depot. Foreign key to :attr:`Depot.id`."""
    depot: Mapped["Depot"] = relationship("Depot", back_populates="areas")

    vehicle_type_id: Mapped[int] = mapped_column(
        ForeignKey("VehicleType.id"), nullable=True
    )
    """The unique identifier of the vehicle type. Foreign key to :attr:`VehicleType.id`.
    If set, only vehicles of this type can be parked in this area. If null, all vehicle types can be parked."""
    vehicle_type: Mapped["VehicleType"] = relationship(
        "VehicleType", back_populates="areas"
    )
    """The vehicle type which can park in this area."""

    area_type = mapped_column(SqlEnum(AreaType, native_enum=False))
    """The type of the area. See :class:`depot.AreaType`."""

    name: Mapped[str] = mapped_column(Text, nullable=True)
    """An optional name for the area. If set, it must be unique within the scenario."""

    name_short: Mapped[str] = mapped_column(Text, nullable=True)
    """An optional short name for the area."""

    capacity: Mapped[int] = mapped_column(Integer)

    capacity_constraint = CheckConstraint(
        "capacity > 0 AND "
        "((area_type = 'DIRECT_TWOSIDE' AND capacity % 2 = 0) "
        "OR (area_type = 'DIRECT_ONESIDE') "
        "OR (area_type = 'LINE'))",
        name="capacity_validity_check",
    )

    processes: Mapped[List["Process"]] = relationship(
        "Process", secondary="AssocAreaProcess", back_populates="areas"
    )

    events: Mapped[List["Event"]] = relationship("Event", back_populates="area")
    """The events that happened in this area."""

    assoc_area_processes: Mapped[List["AssocAreaProcess"]] = relationship(
        "AssocAreaProcess", viewonly=True
    )
    """The association between this area and its processes."""

    _table_args_list.append(capacity_constraint)

    __table_args__ = tuple(_table_args_list)

    def __repr__(self) -> str:
        return f"<Area(id={self.id}, name={self.name}, area_type={self.area_type}, capacity={self.capacity})>"


class Process(Base):
    """A Process represents a certain action that can be executed on a vehicle."""

    __tablename__ = "Process"

    _table_args_list: List[Constraint] = []

    id: Mapped[int] = mapped_column(BigInteger, primary_key=True)
    """The unique identifier of the process. Auto-incremented."""

    scenario_id: Mapped[int] = mapped_column(ForeignKey("Scenario.id"))
    """The unique identifier of the scenario. Foreign key to :attr:`Scenario.id`."""
    scenario: Mapped["Scenario"] = relationship("Scenario", back_populates="processes")
    """The scenario."""

    name: Mapped[str] = mapped_column(Text)
    """A name for the process. If set, it must be unique within the scenario."""

    name_short: Mapped[str] = mapped_column(Text, nullable=True)
    """An optional short name for the process."""

    dispatchable: Mapped[bool] = mapped_column(Boolean)
    """Whether the bus is ready for departure."""

    duration: Mapped[timedelta] = mapped_column(Interval, nullable=True)
    """The duration of this process in seconds."""

    electric_power: Mapped[float] = mapped_column(Float, nullable=True)
    """The peak electric power required by this process in kW. Actual power consumption might be lower. It implies the 
    charging equipment to be provided."""

    availability: Mapped[List[Tuple[datetime, datetime]]] = mapped_column(
        postgresql.JSONB, nullable=True
    )
    """Temporal availability of this process represented by a list of start and end times. Null means this process is 
    always available."""

    plans: Mapped[List["Plan"]] = relationship(
        "Plan",
        secondary="AssocPlanProcess",
        back_populates="processes",
        viewonly=True,
    )

    areas: Mapped[List["Area"]] = relationship(
        "Area",
        secondary="AssocAreaProcess",
        back_populates="processes",
    )

    assoc_area_processes: Mapped[List["AssocAreaProcess"]] = relationship(
        "AssocAreaProcess", viewonly=True
    )

    # This constraint verifies that the process actually does something
    _table_args_list.append(
        CheckConstraint(
            "(duration IS NULL) OR"
            "(duration IS NOT NULL AND duration >= '00:00:00') OR"
            "(electric_power IS NULL) OR"
            "(electric_power IS NOT NULL AND electric_power >= 0)",
            name="positive_duration_and_power_check",
        )
    )

    __table_args__ = tuple(_table_args_list)

    def __repr__(self) -> str:
        return f"<Process(id={self.id}, name={self.name}, duration={self.duration}, electric_power={self.electric_power})>"


class AssocPlanProcess(Base):
    """The association table for the many-to-many relationship between :class:`Plan` and :class:`Process`."""

    __tablename__ = "AssocPlanProcess"

    id = mapped_column(BigInteger, primary_key=True)
    """The unique identifier of the association. Auto-incremented. Needed for django."""

    scenario_id: Mapped[int] = mapped_column(ForeignKey("Scenario.id"))
    """The unique identifier of the scenario. Foreign key to :attr:`Scenario.id`."""
    scenario: Mapped["Scenario"] = relationship(
        "Scenario", back_populates="assoc_plan_processes"
    )
    """The scenario."""

    plan_id: Mapped[int] = mapped_column(ForeignKey("Plan.id"))
    """The unique identifier of the plan. Foreign key to :attr:`Plan.id`."""
    plan: Mapped["Plan"] = relationship("Plan")
    """The plan."""

    process_id: Mapped[int] = mapped_column(ForeignKey("Process.id"))
    """The unique identifier of the process. Foreign key to :attr:`Process.id`."""
    process: Mapped["Process"] = relationship("Process")
    """The process."""

    ordinal: Mapped[int] = mapped_column(Integer)
    """The ordinal of the process in the plan."""

    def __repr__(self) -> str:
        return f"<AssocPlanProcess(id={self.id}, Plan={self.plan}, Process={self.process}, ordinal={self.ordinal})>"


class AssocAreaProcess(Base):
    """The association table for the many-to-many relationship between :class:`Area` and :class:`Process`."""

    __tablename__ = "AssocAreaProcess"

    id = mapped_column(BigInteger, primary_key=True)
    """The unique identifier of the association. Auto-incremented. Needed for django."""

    area_id: Mapped[int] = mapped_column(ForeignKey("Area.id"))
    """The unique identifier of the area. Foreign key to :attr:`Area.id`."""
    area: Mapped["Area"] = relationship("Area", overlaps="areas,processes")
    """The area."""

    process_id: Mapped[int] = mapped_column(ForeignKey("Process.id"))
    """The unique identifier of the process. Foreign key to :attr:`Process.id`."""
    process: Mapped["Process"] = relationship("Process", overlaps="areas,processes")
    """The process."""

    def __repr__(self) -> str:
        return f"<AssocAreaProcess(id={self.id}, area_id={self.area_id}, process_id={self.process_id})>"
