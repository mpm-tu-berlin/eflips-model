from typing import List, TYPE_CHECKING
from enum import Enum as PyEnum, auto

from sqlalchemy import (
    Integer,
    ForeignKey,
    Text,
    Enum as SqlEnum,
    BigInteger,
    CheckConstraint,
)
from sqlalchemy.orm import Mapped, mapped_column, relationship

from eflips.model import Base

if TYPE_CHECKING:
    from eflips.model import Scenario, VehicleType


class Depot(Base):
    """
    The Depot represents a palce where vehicles not engaged in a schedule are parked,
    processed and dispatched.
    """

    __tablename__ = "Depot"
    id: Mapped[int] = mapped_column(Integer, primary_key=True)
    """The unique idenfitier of the depot. Auto-incremented."""

    scenario_id: Mapped[int] = mapped_column(ForeignKey("Scenario.id"))
    """The unique identifier of the scenario. Foreign key to :attr:`Scenario.id`."""
    scenario: Mapped["Scenario"] = relationship("Scenario", back_populates="depots")
    """The scenario this depot belongs to."""

    default_plan_id: Mapped[int] = mapped_column(ForeignKey("Plan.id"))
    """The default plan of this depot. Foreign key to :attr:`Plan.id`."""
    default_plan: Mapped["Plan"] = relationship("Plan", back_populates="depot")

    name: Mapped[str] = mapped_column(Text)
    """A name for the depot."""

    name_short: Mapped[str] = mapped_column(Text, nullable=True)
    """An optional short name for the depot."""

    areas: Mapped[List["Area"]] = relationship("Area", back_populates="depot")
    """The areas of this depot."""


class Plan(Base):
    """
    The Plan represents a certain order of processes, which are executed on vehicles in a depot.
    """

    __tablename__ = "Plan"

    id: Mapped[int] = mapped_column(Integer, primary_key=True)
    """The unique identifier of the plan. Auto-incremented."""

    scenario_id: Mapped[int] = mapped_column(ForeignKey("Scenario.id"))
    """The unique identifier of the scenario. Foreign key to :attr:`Scenario.id`."""
    scenario: Mapped["Scenario"] = relationship("Scenario", back_populates="plans")
    """The scenario this plan belongs to."""

    name: Mapped[str] = mapped_column(Text)
    """A name for the plan."""

    depot: Mapped["Depot"] = relationship("Depot", back_populates="default_plan")


class AreaType(PyEnum):
    """This class represents the type of an area in eFLIPS-Depot"""

    DIRECT_ONESIDE = auto()
    """A direct area where vehicles drive in form one side only."""

    DIRECT_TWOSIDE = auto()
    """A direct area where vehicles drive in form both sides. Also called a "herringbone" configuration."""

    LINE = auto()
    """A line area where vehicles are parked in a line. There might be one or more rows in the area."""


class Area(Base):
    """An Area represents a certain area in a depot, where at least one process is available."""

    __tablename__ = "Area"

    _table_args_list = []

    id: Mapped[int] = mapped_column(Integer, primary_key=True)
    """The unique identifier of the area. Auto-incremented."""

    scenario_id: Mapped[int] = mapped_column(ForeignKey("Scenario.id"))
    """The unique identifier of the scenario. Foreign key to :attr:`Scenario.id`."""
    scenario: Mapped["Scenario"] = relationship("Scenario", back_populates="areas")
    """The scenario this area belongs to."""

    depot_id: Mapped[int] = mapped_column(ForeignKey("Depot.id"))
    """The unique identifier of the depot. Foreign key to :attr:`Depot.id`."""
    depot: Mapped["Depot"] = relationship("Depot", back_populates="areas")

    vehicle_type_id: Mapped[int] = mapped_column(ForeignKey("VehicleType.id"))
    """The unique identifier of the vehicle type. Foreign key to :attr:`VehicleType.id`."""
    vehicle_type: Mapped["VehicleType"] = relationship(
        "VehicleType", back_populates="area"
    )
    """The vehicle type which can park in this area."""

    type = mapped_column(SqlEnum(AreaType))
    """The type of the area. See :class:`depot.AreaType`."""

    row_count: Mapped[int] = mapped_column(BigInteger)

    row_count_constraint = CheckConstraint("type = 'LINE' AND row_count > 0")
    _table_args_list.append(row_count_constraint)

    capacity: Mapped[int] = mapped_column(BigInteger)

    capacity_constraint = CheckConstraint(
        "capacity > 0 AND "
        "((type = 'DIRECT_TWOSIDE' AND capacity % 2 = 0) "
        "OR (type = 'DIRECT_ONESIDE') "
        "OR (type = 'LINE' AND capacity % row_count = 0))"

    )

    _table_args_list.append(capacity_constraint)

    name: Mapped[str] = mapped_column(Text)
    """A name for the area."""

    __table_args__ = tuple(_table_args_list)
