import importlib

import sqlalchemy
from sqlalchemy.orm import DeclarativeBase


class Base(DeclarativeBase):
    pass


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
