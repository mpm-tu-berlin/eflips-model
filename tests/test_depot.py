import os

import pytest
import sqlalchemy
from sqlalchemy import create_engine
from sqlalchemy.orm import Session

from eflips.model import Depot, Plan, Area, VehicleType, AreaType

from tests.test_general import TestGeneral


class TestDepot(TestGeneral):
    def test_create_depot(self, session, scenario):
        # Create a simple depot

        depot = Depot(scenario=scenario, name="Test Depot")
        session.add(depot)

        plan = Plan(scenario=scenario, name="Test Plan", depot=depot)
        session.add(plan)

        depot.default_plan = plan

        area = Area(scenario=scenario, name="Test Area", depot=depot,
                    type=AreaType.LINE, row_count=2, capacity=6)
        session.add(area)

        test_vehicle_type = VehicleType(
            scenario=scenario,
            name="Test Vehicle Type 2",
            battery_capacity=100,
            charging_curve=[[0, 150], [1, 150]],
            opportunity_charge_capable=True,
        )
        area.vehicle_type = test_vehicle_type

        session.commit()

class TestArea(TestGeneral):
    def test_invalid_area(self, session, scenario):

        # Test line area with invalid capacity
        with pytest.raises(sqlalchemy.exc.IntegrityError):
            area = Area(scenario=scenario, name="Test Area 1", depot=None,
                        type=AreaType.LINE, row_count=2, capacity=5)
            session.add(area)
            session.commit()
        session.rollback()

        # Test direct area with negative capacity
        with pytest.raises(sqlalchemy.exc.IntegrityError):
            area = Area(scenario=scenario, name="Test Area 2", depot=None,
                        type=AreaType.DIRECT_ONESIDE, capacity=-1)
            session.add(area)
            session.commit()
        session.rollback()


        # Test direct area with odd capacity
        with pytest.raises(sqlalchemy.exc.IntegrityError):
            area = Area(scenario=scenario, name="Test Area 3", depot=None,
                        type=AreaType.DIRECT_TWOSIDE, capacity=17)
            session.add(area)
            session.commit()
        session.rollback()




