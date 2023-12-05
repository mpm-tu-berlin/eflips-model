from datetime import timedelta

import pytest
import sqlalchemy

from eflips.model import Area, AreaType, Depot, Plan, Process, Scenario, VehicleType
from tests.test_general import TestGeneral


class TestDepot(TestGeneral):
    @pytest.fixture()
    def depot_with_content(self, session, scenario):
        # Create a simple depot

        depot = Depot(scenario=scenario, name="Test Depot", name_short="TD")
        session.add(depot)

        # Create plan

        plan = Plan(scenario=scenario, name="Test Plan")
        session.add(plan)

        depot.default_plan = plan

        # Create area
        area = Area(
            scenario=scenario,
            name="Test Area",
            depot=depot,
            area_type=AreaType.LINE,
            row_count=2,
            capacity=6,
        )
        session.add(area)

        # Create vehicle type for area
        test_vehicle_type = VehicleType(
            scenario=scenario,
            name="Test Vehicle Type 2",
            battery_capacity=100,
            charging_curve=[[0, 150], [1, 150]],
            opportunity_charging_capable=True,
        )
        area.vehicle_type = test_vehicle_type

        # Create processes
        clean = Process(
            name="Clean",
            scenario=scenario,
            dispatchable=False,
            duration=timedelta(minutes=30),
        )

        charging = Process(
            name="Charging",
            scenario=scenario,
            dispatchable=False,
            electric_power=150,
        )

        session.add(clean)
        session.add(charging)

        area.processes.append(clean)
        area.processes.append(charging)

        plan.processes.append(clean)
        plan.processes.append(charging)

        session.commit()

        # Test reverse relationships

        assert depot.default_plan == plan
        assert depot.areas == [area]
        assert clean.areas == [area]
        assert clean.plans == [plan]

        return depot


class TestArea(TestDepot):
    def test_create_area(self, depot_with_content, session, scenario):
        vehicle_type = VehicleType(
            scenario=scenario,
            name="Test Vehicle Type 2",
            battery_capacity=100,
            charging_curve=[[0, 150], [1, 150]],
            opportunity_charging_capable=True,
        )

        line_area = Area(
            scenario=scenario,
            depot=depot_with_content,
            name="line area",
            area_type=AreaType.LINE,
            row_count=2,
            capacity=6,
        )

        session.add(line_area)
        line_area.vehicle_type = vehicle_type

        direct_twoside_area = Area(
            scenario=scenario,
            depot=depot_with_content,
            name="direct two side Area",
            area_type=AreaType.DIRECT_TWOSIDE,
            capacity=4,
        )
        direct_twoside_area.vehicle_type = vehicle_type
        session.add(direct_twoside_area)

        direct_oneside_area = Area(
            scenario=scenario,
            depot=depot_with_content,
            name="direct one side",
            area_type=AreaType.DIRECT_ONESIDE,
            capacity=7,
        )
        direct_oneside_area.vehicle_type = vehicle_type
        session.add(direct_oneside_area)
        session.commit()

    def test_invalid_area(self, depot_with_content, session, scenario):
        # Test line area with invalid capacity

        vehicle_type = VehicleType(
            scenario=scenario,
            name="Test Vehicle Type 2",
            battery_capacity=100,
            charging_curve=[[0, 150], [1, 150]],
            opportunity_charging_capable=True,
        )

        with pytest.raises(sqlalchemy.exc.IntegrityError):
            area = Area(
                scenario=scenario,
                name="Test Area 1",
                depot=depot_with_content,
                area_type=AreaType.LINE,
                row_count=2,
                capacity=5,
            )
            session.add(area)
            area.vehicle_type = vehicle_type
            session.commit()
        session.rollback()

        # Test direct area with negative capacity
        with pytest.raises(sqlalchemy.exc.IntegrityError):
            area = Area(
                scenario=scenario,
                name="Test Area 2",
                depot=depot_with_content,
                area_type=AreaType.DIRECT_ONESIDE,
                capacity=-5,
            )
            session.add(area)
            area.vehicle_type = vehicle_type
            session.commit()
        session.rollback()

        # Test direct area with odd capacity
        with pytest.raises(sqlalchemy.exc.IntegrityError):
            area = Area(
                scenario=scenario,
                name="Test Area 3",
                depot=depot_with_content,
                area_type=AreaType.DIRECT_TWOSIDE,
                capacity=17,
            )
            session.add(area)
            area.vehicle_type = vehicle_type
            session.commit()
        session.rollback()

    def test_copy_depot(self, depot_with_content, scenario, session):
        session.add(depot_with_content)
        session.commit()

        # Clone the scenario
        scenario_clone = scenario.clone(session)
        session.add(scenario_clone)
        session.commit()

        # Load the depot
        depot = (
            session.query(Depot)
            .join(Scenario)
            .filter(Depot.scenario == scenario_clone)
            .one()
        )

        assert depot.scenario == scenario_clone
        assert depot.default_plan.scenario == scenario_clone

        for area in depot.areas:
            assert area.scenario == scenario_clone
            assert area.vehicle_type.scenario == scenario_clone
            assert area.depot == depot
            for process in area.processes:
                assert process.scenario == scenario_clone
                for plan in process.plans:
                    assert plan.scenario == scenario_clone

        session.delete(scenario)
        session.commit()

        assert depot.scenario == scenario_clone
        assert depot.default_plan.scenario == scenario_clone

        for area in depot.areas:
            assert area.scenario == scenario_clone
            assert area.vehicle_type.scenario == scenario_clone
            assert area.depot == depot
            for process in area.processes:
                assert process.scenario == scenario_clone
                for plan in process.plans:
                    assert plan.scenario == scenario_clone


class TestProcess(TestGeneral):
    def test_create_process(self, session, scenario):
        # create a valid process
        process = Process(
            name="Test Process",
            scenario=scenario,
            dispatchable=False,
            duration=timedelta(minutes=30),
            electric_power=150,
        )

        session.add(process)
        session.commit()

        process = Process(
            name="Test Process",
            scenario=scenario,
            dispatchable=False,
            duration=timedelta(minutes=30),
        )

        session.add(process)
        session.commit()

        process = Process(
            name="Test Process",
            scenario=scenario,
            dispatchable=False,
            electric_power=150,
        )
        session.add(process)
        session.commit()

        # test invalid process with negative duration and power
        with pytest.raises(sqlalchemy.exc.IntegrityError):
            process = Process(
                name="Test Process",
                scenario=scenario,
                dispatchable=False,
                duration=timedelta(minutes=-30),
                electric_power=-150,
            )
            session.add(process)
            session.commit()
        session.rollback()

    def test_process_plan(self, session, scenario):
        process = Process(
            name="Test Process",
            scenario=scenario,
            dispatchable=False,
            duration=timedelta(minutes=30),
        )

        session.add(process)
        session.commit()

        # add a plan
        plan = Plan(scenario=scenario, name="Test Plan")

        session.add(plan)
        plan.processes.append(process)
        session.commit()

        assert process.plans == [plan]
