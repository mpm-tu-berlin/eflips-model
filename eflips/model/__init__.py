from sqlalchemy.orm import DeclarativeBase


class Base(DeclarativeBase):
    pass


# Strict re-exports make MyPy happy
# And they need to be below the Base() to prevent circular imports
from eflips.model.general import BatteryType as BatteryType
from eflips.model.general import Scenario as Scenario
from eflips.model.general import Vehicle as Vehicle
from eflips.model.general import VehicleClass as VehicleClass
from eflips.model.general import VehicleType as VehicleType
from eflips.model.network import ChargeType as ChargeType
from eflips.model.network import Line as Line
from eflips.model.network import Route as Route
from eflips.model.network import Station as Station
from eflips.model.network import StopTime as StopTime
from eflips.model.network import VoltageLevel as VoltageLevel
from eflips.model.network import Trip as Trip
from eflips.model.network import StopTime as StopTime
from eflips.model.network import TripType as TripType
