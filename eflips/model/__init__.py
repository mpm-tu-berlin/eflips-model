import datetime
import importlib
from typing import Any

import sqlalchemy
from geoalchemy2 import load_spatialite
from sqlalchemy.event import listen
from sqlalchemy.orm import DeclarativeBase


def create_engine(url: str, **kwargs) -> sqlalchemy.Engine:  # type: ignore
    """
    Create a SQLAlchemy engine with the given URL and options. This is an overridden version of the
    `sqlalchemy.create_engine` function that loads the Spatialite extension if sqlite is used.

    :param url: The database URL to connect to.
    :param kwargs: Additional keyword arguments for the engine creation.
    :return: A SQLAlchemy engine instance.
    """
    engine = sqlalchemy.create_engine(url, **kwargs)
    if url.startswith("sqlite://"):
        listen(engine, "connect", load_spatialite)
    return engine


class Base(DeclarativeBase):
    pass


class TimeStampWithTz(sqlalchemy.types.TypeDecorator):  # type: ignore
    """
    A SQLAlchemy TypeDecorator that handles timezone-aware datetime objects.

    This decorator enables storing timezone-aware datetime objects in databases
    that don't support timezone information (like SQLite). It works by:

    1. On save: Converting timezone-aware datetimes to UTC and storing them
       as naive datetimes (without timezone info)
    2. On load: Treating stored naive datetimes as UTC and converting them
       to the system's local timezone

    Example:
        class MyModel(Base):
            __tablename__ = 'my_table'
            id = Column(Integer, primary_key=True)
            created_at = Column(TimeStampWithTz, nullable=False)

        # Usage - always use timezone-aware datetimes
        model = MyModel(created_at=datetime.datetime.now(datetime.timezone.utc))
    """

    impl = sqlalchemy.types.DateTime

    def process_bind_param(
        self, value: datetime.datetime | None, dialect: Any
    ) -> datetime.datetime | None:
        """
        Convert a timezone-aware datetime to a naive UTC datetime for storage.

        Args:
            value: A timezone-aware datetime object or None
            dialect: The database dialect (unused but required by interface)

        Returns:
            A naive datetime in UTC, or None if value is None

        Raises:
            ValueError: If value is not a datetime object or lacks timezone info
        """
        if value is None:
            return None

        # Validate input type
        if not isinstance(value, datetime.datetime):
            raise ValueError(
                f"Expected a datetime object, got {type(value).__name__} instead."
            )

        # Ensure timezone awareness
        if value.tzinfo is None:
            raise ValueError(
                "Datetime must be timezone-aware. "
                "Use datetime.now(timezone.utc) or datetime.fromisoformat() with timezone."
            )

        # Convert to UTC and remove timezone info for storage
        return value.astimezone(datetime.timezone.utc).replace(tzinfo=None)

    def process_result_value(
        self, value: datetime.datetime | None, dialect: Any
    ) -> datetime.datetime | None:
        """
        Convert a naive UTC datetime from storage to a timezone-aware local datetime.

        Args:
            value: A naive datetime object (assumed UTC) or None
            dialect: The database dialect (unused but required by interface)

        Returns:
            A timezone-aware datetime in the local timezone, or None if value is None

        Raises:
            ValueError: If value is not a datetime object or has timezone info
        """
        if value is None:
            return None

        # Validate retrieved type
        if not isinstance(value, datetime.datetime):
            raise ValueError(
                f"Expected a datetime object from database, got {type(value).__name__} instead."
            )

        # Ensure the database stored it without timezone (as expected)
        if value.tzinfo is not None:
            raise ValueError(
                "Database returned datetime with timezone info, but expected naive datetime. "
                "Check database configuration."
            )

        # Interpret as UTC and convert to local timezone
        utc_datetime = value.replace(tzinfo=datetime.timezone.utc)

        # Get local timezone more efficiently
        local_tz = datetime.datetime.now().astimezone().tzinfo

        return utc_datetime.astimezone(local_tz)


class ConsistencyWarning(UserWarning):
    """
    A warning that is raised when a consistency check fails.
    """

    pass


def setup_database(engine: sqlalchemy.Engine) -> None:
    """
    Use this method to create a new database from scratch.

    This method will create all tables and set the alembric version to the latest version, based on this howto:
    https://alembic.sqlalchemy.org/en/latest/cookbook.html#building-an-up-to-date-database-from-scratch

    :param engine: The engine to use to connect to the database.

    :return: None
    """
    Base.metadata.create_all(engine)

    from alembic.config import Config
    from alembic import command

    alembic_cfg = Config(
        str(importlib.resources.files("eflips.model").joinpath("alembic.ini"))
    )
    alembic_cfg.set_main_option("sqlalchemy.url", str(engine.url))
    alembic_cfg.set_main_option(
        "script_location",
        str(importlib.resources.files("eflips.model").joinpath("migrations")),
    )
    command.stamp(alembic_cfg, "head")


# Strict re-exports make MyPy happy
# And they need to be below the Base() to prevent circular imports
from eflips.model.general import BatteryType as BatteryType
from eflips.model.general import Scenario as Scenario
from eflips.model.general import Vehicle as Vehicle
from eflips.model.general import VehicleClass as VehicleClass
from eflips.model.general import VehicleType as VehicleType
from eflips.model.general import Event as Event
from eflips.model.general import EventType as EventType
from eflips.model.general import (
    AssocVehicleTypeVehicleClass as AssocVehicleTypeVehicleClass,
)
from eflips.model.general import ConsumptionLut as ConsumptionLut
from eflips.model.general import Temperatures as Temperatures
from eflips.model.general import ChargingPointType as ChargingPointType

from eflips.model.network import ChargeType as ChargeType
from eflips.model.network import Line as Line
from eflips.model.network import Route as Route
from eflips.model.network import Station as Station
from eflips.model.network import VoltageLevel as VoltageLevel
from eflips.model.network import AssocRouteStation as AssocRouteStation

from eflips.model.schedule import StopTime as StopTime
from eflips.model.schedule import TripType as TripType
from eflips.model.schedule import Trip as Trip
from eflips.model.schedule import Rotation as Rotation

from eflips.model.depot import Depot as Depot
from eflips.model.depot import Plan as Plan
from eflips.model.depot import Area as Area
from eflips.model.depot import AreaType as AreaType
from eflips.model.depot import Process as Process
from eflips.model.depot import AssocPlanProcess as AssocPlanProcess
from eflips.model.depot import AssocAreaProcess as AssocAreaProcess
