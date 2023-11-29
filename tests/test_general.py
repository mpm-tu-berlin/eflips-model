import copy

import psycopg2
import pytest
import sqlalchemy
from sqlalchemy import create_engine
import os

from sqlalchemy.orm import Session

from eflips.model import Base, VehicleType, BatteryType, Vehicle

from eflips.model import Scenario


class TestGeneral:
    @pytest.fixture()
    def scenario(self, session):
        """
        Creates a scenario
        :param session: An SQLAlchemy Session with the eflips-db schema
        :return: A :class:`Scenario` object
        """
        scenario = Scenario(name="Test Scenario")
        session.add(scenario)
        session.commit()
        return scenario

    @pytest.fixture()
    def sample_content(self, session):
        """
        Creates a scenario that comes filled with sample content for each type
        :param session: An SQLAlchemy Session with the eflips-db schema
        :return: A :class:`Scenario` object
        """

        # Add a scenario
        scenario = Scenario(name="Test Scenario")
        session.add(scenario)

        # Add a vehicle type with a battery type
        vehicle_type = VehicleType(
            scenario=scenario,
            name="Test Vehicle Type",
            battery_capacity=100,
            charging_curve=[[0, 150], [1, 150]],
            opportunity_charge_capable=True,
        )
        session.add(vehicle_type)
        battery_type = BatteryType(
            scenario=scenario, specific_mass=100, chemistry={"test": "test"}
        )
        session.add(battery_type)
        vehicle_type.battery_type = battery_type

        # Add a vehicle type without a battery type
        vehicle_type = VehicleType(
            scenario=scenario,
            name="Test Vehicle Type 2",
            battery_capacity=100,
            charging_curve=[[0, 150], [1, 150]],
            opportunity_charge_capable=True,
        )
        session.add(vehicle_type)

        # Add a vehicle
        vehicle = Vehicle(
            scenario=scenario,
            vehicle_type=vehicle_type,
            name="Test Vehicle",
            name_short="TV",
        )
        session.add(vehicle)

        session.commit()
        return scenario

    @pytest.fixture()
    def session(self):
        """
        Creates a session with the eflips-db schema
        NOTE: THIS DELETE ALL DATA IN THE DATABASE
        :return: an SQLAlchemy Session with the eflips-db schema
        """
        url = os.environ["DATABASE_URL"]
        engine = create_engine(
            url, echo=False
        )  # Change echo to True to see SQL queries
        Base.metadata.drop_all(engine)
        Base.metadata.create_all(engine)
        session = Session(bind=engine)
        yield session
        session.close()


class TestScenario(TestGeneral):
    def test_create_scenario(self, session):
        scenario = Scenario(name="Test Scenario")
        session.add(scenario)
        session.flush()
        session.commit()
        assert scenario.id == 1
        assert scenario.name == "Test Scenario"
        assert scenario.created is not None
        assert scenario.finished is None
        assert scenario.simba_options is None

    def test_copy_scenario(self, session, sample_content):
        cloned_scenario = sample_content.clone(session)
        # Make sure that all links are also pointing back to the cloned scenario
        assert cloned_scenario.id == 2
        for vehicle_type in cloned_scenario.vehicle_types:
            assert vehicle_type.scenario == cloned_scenario
            if vehicle_type.battery_type is not None:
                assert vehicle_type.battery_type.scenario == cloned_scenario

        for battery_type in cloned_scenario.battery_types:
            assert battery_type.scenario == cloned_scenario

    def test_delete_scenario(self, session, sample_content):
        session.delete(sample_content)
        session.commit()
        assert session.query(Scenario).count() == 0
        assert session.query(VehicleType).count() == 0
        assert session.query(BatteryType).count() == 0

    def test_delete_child_scenario(self, session, sample_content):
        cloned_scenario = sample_content.clone(session)
        assert session.query(Scenario).count() == 2
        assert session.query(VehicleType).count() == 4
        assert session.query(BatteryType).count() == 2
        session.delete(cloned_scenario)
        session.commit()
        assert session.query(Scenario).count() == 1
        assert session.query(VehicleType).count() == 2
        assert session.query(BatteryType).count() == 1

    def test_delete_parent_scenario(self, session, sample_content):
        cloned_scenario = sample_content.clone(session)
        assert session.query(Scenario).count() == 2
        assert session.query(VehicleType).count() == 4
        assert session.query(BatteryType).count() == 2

        # For some reason, we need to commit the child scenario first
        session.commit()
        session.delete(sample_content)

        assert session.query(Scenario).count() == 1
        assert session.query(VehicleType).count() == 2
        assert session.query(BatteryType).count() == 1

    def test_create_scenario_with_parent(self, session):
        parent = Scenario(name="Parent Scenario")
        session.add(parent)
        session.commit()
        scenario = Scenario(name="Child Scenario", parent=parent)
        session.add(scenario)
        session.commit()
        assert scenario.id == 2
        assert scenario.name == "Child Scenario"
        assert scenario.created is not None
        assert scenario.finished is None
        assert scenario.simba_options is None
        assert scenario.parent == parent
        assert scenario.parent_id == 1
        assert parent.children == [scenario]


class TestVehicleType(TestGeneral):
    def test_create_vehicle_type(self, session, scenario):
        # Create a simple vehicle type, with only the required fields
        vehicle_type = VehicleType(
            name="Test Vehicle Type",
            scenario=scenario,
            battery_capacity=100,
            charging_curve=[[0, 150], [1, 150]],
            opportunity_charge_capable=True,
        )
        session.add(vehicle_type)
        session.commit()

        # Create one with all fields
        battery_type = BatteryType(
            scenario=scenario, specific_mass=100, chemistry={"test": "test"}
        )
        vehicle_type = VehicleType(
            name="Test Vehicle Type",
            scenario=scenario,
            battery_type=battery_type,
            battery_capacity=100,
            battery_capacity_reserve=10,
            charging_curve=[[0, 150], [1, 150]],
            v2g_curve=[[0, 150], [1, 150]],
            charging_efficiency=0.9,
            opportunity_charge_capable=True,
            minimum_charging_power=10,
            shape=(2, 4, 12),
            empty_mass=12000,
        )
        session.add(vehicle_type)
        session.commit()

    def test_create_vehicle_type_invalid_battery_capacity(self, scenario, session):
        for battery_capacity in [-100, 0]:
            with pytest.raises(sqlalchemy.exc.IntegrityError):
                vehicle_type = VehicleType(
                    name="Test Vehicle Type",
                    scenario=scenario,
                    battery_capacity=battery_capacity,
                    charging_curve=[[0, 150], [1, 150]],
                    opportunity_charge_capable=True,
                )
                session.add(vehicle_type)
                session.commit()
            session.rollback()

    def test_create_vehicle_type_invalid_battery_capacity_reserve(
        self, scenario, session
    ):
        with pytest.raises(sqlalchemy.exc.IntegrityError):
            vehicle_type = VehicleType(
                name="Test Vehicle Type",
                scenario=scenario,
                battery_capacity=100,
                battery_capacity_reserve=-10,
                charging_curve=[[0, 150], [1, 150]],
                opportunity_charge_capable=True,
            )
            session.add(vehicle_type)
            session.commit()
        session.rollback()

        # For reserve capacity, 0 is valid
        vehicle_type = VehicleType(
            name="Test Vehicle Type",
            scenario=scenario,
            battery_capacity=100,
            battery_capacity_reserve=0,
            charging_curve=[[0, 150], [1, 150]],
            opportunity_charge_capable=True,
        )
        session.add(vehicle_type)
        session.commit()

    def test_create_vehicle_type_invalid_charging_efficiency(self, scenario, session):
        for charging_efficiency in (-1, 0, 1.1):
            with pytest.raises(sqlalchemy.exc.IntegrityError):
                vehicle_type = VehicleType(
                    name="Test Vehicle Type",
                    scenario=scenario,
                    battery_capacity=100,
                    charging_curve=[[0, 150], [1, 150]],
                    charging_efficiency=charging_efficiency,
                    opportunity_charge_capable=True,
                )
                session.add(vehicle_type)
                session.commit()
            session.rollback()

    def test_create_vehicle_type_invalid_minimum_charging_power(
        self, scenario, session
    ):
        with pytest.raises(sqlalchemy.exc.IntegrityError):
            vehicle_type = VehicleType(
                name="Test Vehicle Type",
                scenario=scenario,
                battery_capacity=100,
                charging_curve=[[0, 150], [1, 150]],
                opportunity_charge_capable=True,
                minimum_charging_power=-10,
            )
            session.add(vehicle_type)
            session.commit()

    def test_create_vehicle_type_invalid_empty_weight(self, scenario, session):
        for empty_weight in (-100, 0):
            with pytest.raises(sqlalchemy.exc.IntegrityError):
                vehicle_type = VehicleType(
                    name="Test Vehicle Type",
                    scenario=scenario,
                    battery_capacity=100,
                    charging_curve=[[0, 150], [1, 150]],
                    opportunity_charge_capable=True,
                    empty_mass=empty_weight,
                )
                session.add(vehicle_type)
                session.commit()
            session.rollback()


class TestBatteryType(TestGeneral):
    def test_create_battery_type(self, session, scenario):
        battery_type = BatteryType(
            scenario=scenario, specific_mass=100, chemistry={"test": "test"}
        )
        session.add(battery_type)
        session.commit()
