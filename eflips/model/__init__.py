from sqlalchemy.orm import DeclarativeBase


class Base(DeclarativeBase):
    pass


from eflips.model.general import Scenario, VehicleType, BatteryType, Vehicle
