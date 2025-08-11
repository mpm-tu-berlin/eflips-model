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
    impl = sqlalchemy.types.DateTime

    def process_bind_param(self, value: datetime.datetime, dialect: Any) -> datetime.datetime | None:  # type: ignore
        if value is None:
            return None

        # Ensure the value is a datetime object
        if not isinstance(value, datetime.datetime):
            raise ValueError(f"Expected a datetime object, got {type(value)} instead.")

        if value.tzinfo is None:
            raise ValueError(
                "The value must be timezone-aware. Please use a timezone-aware datetime object."
            )

        # Convert to UTC before and remove the timezone info (implicit UTC)
        value_no_tz = value.astimezone(datetime.timezone.utc).replace(tzinfo=None)
        return value_no_tz

    def process_result_value(
        self, value: datetime.datetime | None, dialect: Any
    ) -> datetime.datetime | None:
        if value is None:
            return None

        # The value was implicit UTC. Make it explicit localtime.
        if not isinstance(value, datetime.datetime):
            raise ValueError(f"Expected a datetime object, got {type(value)} instead.")

        if value.tzinfo is not None:
            raise ValueError(
                "We expect the database to store the value without timezone information."
            )

        value_with_tz = value.replace(tzinfo=datetime.timezone.utc)

        local_timezone = (
            datetime.datetime.now(datetime.timezone.utc).astimezone().tzinfo
        )

        return value_with_tz.astimezone(local_timezone)


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
from eflips.model.schedule import Block as Block
from eflips.model.schedule import Rotation as Rotation  # Deprecated, use Block instead

from eflips.model.depot import Depot as Depot
from eflips.model.depot import Plan as Plan
from eflips.model.depot import Area as Area
from eflips.model.depot import AreaType as AreaType
from eflips.model.depot import Process as Process
from eflips.model.depot import AssocPlanProcess as AssocPlanProcess
from eflips.model.depot import AssocAreaProcess as AssocAreaProcess
