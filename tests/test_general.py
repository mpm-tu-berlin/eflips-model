import os
from datetime import datetime, timedelta, timezone

import pytest
import sqlalchemy
from sqlalchemy import create_engine
from sqlalchemy.orm import Session

from eflips.model import (
    AssocRouteStation,
    Base,
    BatteryType,
    Event,
    EventType,
    Line,
    Rotation,
    Route,
    Scenario,
    Station,
    StopTime,
    Trip,
    TripType,
    Vehicle,
    VehicleClass,
    VehicleType,
)
from eflips.model.general import AssocVehicleTypeVehicleClass


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

        # Add a VehicleClass
        vehicle_class = VehicleClass(
            scenario=scenario,
            name="Test Vehicle Class",
            vehicle_types=[vehicle_type],
        )
        session.add(vehicle_class)

        # Add a vehicle
        vehicle = Vehicle(
            scenario=scenario,
            vehicle_type=vehicle_type,
            name="Test Vehicle",
            name_short="TV",
        )
        session.add(vehicle)

        line = Line(
            scenario=scenario,
            name="Test Line",
            name_short="TL",
        )
        session.add(line)

        stop_1 = Station(
            scenario=scenario,
            name="Test Station 1",
            name_short="TS1",
            location="POINT(0 0)",
            is_electrified=False,
        )
        session.add(stop_1)

        stop_2 = Station(
            scenario=scenario,
            name="Test Station 2",
            name_short="TS2",
            location="POINT(1 0)",
            is_electrified=False,
        )
        session.add(stop_2)

        stop_3 = Station(
            scenario=scenario,
            name="Test Station 3",
            name_short="TS3",
            location="POINT(2 0)",
            is_electrified=False,
        )

        route_1 = Route(
            scenario=scenario,
            name="Test Route 1",
            name_short="TR1",
            departure_station=stop_1,
            arrival_station=stop_3,
            line=line,
            distance=1000,
        )
        assocs = [
            AssocRouteStation(
                scenario=scenario, station=stop_1, route=route_1, elapsed_distance=0
            ),
            AssocRouteStation(
                scenario=scenario, station=stop_2, route=route_1, elapsed_distance=500
            ),
            AssocRouteStation(
                scenario=scenario, station=stop_3, route=route_1, elapsed_distance=1000
            ),
        ]
        route_1.assoc_route_stations = assocs
        session.add(route_1)

        route_2 = Route(
            scenario=scenario,
            name="Test Route 2",
            name_short="TR2",
            departure_station=stop_3,
            arrival_station=stop_1,
            line=line,
            distance=1000,
        )
        assocs = [
            AssocRouteStation(
                scenario=scenario, station=stop_3, route=route_2, elapsed_distance=0
            ),
            AssocRouteStation(
                scenario=scenario, station=stop_2, route=route_2, elapsed_distance=500
            ),
            AssocRouteStation(
                scenario=scenario, station=stop_1, route=route_2, elapsed_distance=1000
            ),
        ]
        route_2.assoc_route_stations = assocs
        session.add(route_2)

        # Add the schedule objects
        first_departure = datetime(
            year=2020, month=1, day=1, hour=12, minute=0, second=0, tzinfo=timezone.utc
        )
        interval = timedelta(minutes=30)
        duration = timedelta(minutes=20)
        trips = []

        rotation = Rotation(
            scenario=scenario,
            trips=trips,
            vehicle_type=vehicle_type,
            allow_opportunity_charging=False,
        )
        session.add(rotation)

        for i in range(15):
            # forward
            trips.append(
                Trip(
                    scenario=scenario,
                    route=route_1,
                    trip_type=TripType.PASSENGER,
                    departure_time=first_departure + 2 * i * interval,
                    arrival_time=first_departure + 2 * i * interval + duration,
                    rotation=rotation,
                )
            )
            stop_times = [
                StopTime(
                    scenario=scenario,
                    station=stop_1,
                    arrival_time=first_departure + 2 * i * interval,
                ),
                StopTime(
                    scenario=scenario,
                    station=stop_2,
                    arrival_time=first_departure
                    + 2 * i * interval
                    + timedelta(minutes=5),
                ),
                StopTime(
                    scenario=scenario,
                    station=stop_3,
                    arrival_time=first_departure + 2 * i * interval + duration,
                ),
            ]
            trips[-1].stop_times = stop_times

            # backward
            trips.append(
                Trip(
                    scenario=scenario,
                    route=route_2,
                    trip_type=TripType.PASSENGER,
                    departure_time=first_departure + (2 * i + 1) * interval,
                    arrival_time=first_departure + (2 * i + 1) * interval + duration,
                    rotation=rotation,
                )
            )
            stop_times = [
                StopTime(
                    scenario=scenario,
                    station=stop_3,
                    arrival_time=first_departure + (2 * i + 1) * interval,
                ),
                StopTime(
                    scenario=scenario,
                    station=stop_2,
                    arrival_time=first_departure
                    + (2 * i + 1) * interval
                    + timedelta(minutes=5),
                ),
                StopTime(
                    scenario=scenario,
                    station=stop_1,
                    arrival_time=first_departure + (2 * i + 1) * interval + duration,
                ),
            ]
            trips[-1].stop_times = stop_times
        session.add_all(trips)

        # TODO: Add a depot

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


class TestVehicleClass(TestGeneral):
    def test_create_vehicle_class(self, session, scenario):
        # Add a VehicleClass
        vehicle_class = VehicleClass(
            scenario=scenario,
            name="Test Vehicle Class",
        )
        session.add(vehicle_class)
        session.commit()

        # Add a vehicle type
        vehicle_type = VehicleType(
            scenario=scenario,
            name="Test Vehicle Type",
            battery_capacity=100,
            charging_curve=[[0, 150], [1, 150]],
            opportunity_charge_capable=True,
        )
        session.add(vehicle_type)

        vehicle_type.vehicle_classes.append(vehicle_class)
        session.commit()

        # Check the reverse relationship
        assert vehicle_class.vehicle_types == [vehicle_type]

        # Check the association table
        assert session.query(AssocVehicleTypeVehicleClass).count() == 1

    def test_vehicle_class_copy_scenarion(self, session, scenario):
        # Add a VehicleClass
        vehicle_class = VehicleClass(
            scenario=scenario,
            name="Test Vehicle Class",
        )
        session.add(vehicle_class)
        session.commit()

        # Add a vehicle type
        vehicle_type = VehicleType(
            scenario=scenario,
            name="Test Vehicle Type",
            battery_capacity=100,
            charging_curve=[[0, 150], [1, 150]],
            opportunity_charge_capable=True,
        )
        session.add(vehicle_type)

        vehicle_type.vehicle_classes.append(vehicle_class)
        session.commit()

        # Copy the scenario
        cloned_scenario = scenario.clone(session)
        session.commit()

        # Load the vehicle type and class in the new scenario
        cloned_vehicle_type = cloned_scenario.vehicle_types[0]
        cloned_vehicle_class = cloned_scenario.vehicle_classes[0]

        # Check the forward relationship
        assert cloned_vehicle_type.vehicle_classes == [cloned_vehicle_class]
        # Check the reverse relationship
        assert cloned_vehicle_class.vehicle_types == [cloned_vehicle_type]
        # Check the association table
        assert session.query(AssocVehicleTypeVehicleClass).count() == 2

        # Delete the parent scenario
        session.delete(scenario)
        session.commit()

        # Check the forward relationship
        assert cloned_vehicle_type.vehicle_classes == [cloned_vehicle_class]
        # Check the reverse relationship
        assert cloned_vehicle_class.vehicle_types == [cloned_vehicle_type]
        # Check the association table
        assert session.query(AssocVehicleTypeVehicleClass).count() == 1


class TestEvent(TestGeneral):
    def test_create_driving_event_simple(self, session, sample_content):
        # Create a driving event on the first trip
        event = Event(
            scenario=session.query(Scenario).first(),
            trip=session.query(Trip).first(),
            vehicle_type=session.query(VehicleType).first(),
            event_type=EventType.DRIVING,
            time_start=session.query(Trip).first().departure_time,
            time_end=session.query(Trip).first().arrival_time,
        )
        session.add(event)
        session.commit()

    def test_create_charging_opportunity(self, session, sample_content):
        event = Event(
            scenario=session.query(Scenario).first(),
            station=session.query(Station).first(),
            subloc_no=1,
            vehicle_type=session.query(VehicleType).first(),
            event_type=EventType.CHARGING_OPPORTUNITY,
            time_start=session.query(Trip).first().departure_time,
            time_end=session.query(Trip).first().arrival_time,
        )
        session.add(event)
        session.commit()

    @pytest.mark.skip(reason="Not implemented yet")
    def test_create_invalid_event_type_combination(self, session, sample_content):
        # At a station it can only be CHARGING_OPPORTUNITY
        for event_type in (
            EventType.DRIVING,
            EventType.CHARGING_DEPOT,
            EventType.SERVICE,
            EventType.STANDBY_DEPARTURE,
            EventType.PRECONDITIONING,
        ):
            event = Event(
                scenario=session.query(Scenario).first(),
                station=session.query(Station).first(),
                subloc_no=1,
                vehicle_type=session.query(VehicleType).first(),
                event_type=event_type,
                time_start=session.query(Trip).first().departure_time,
                time_end=session.query(Trip).first().arrival_time,
            )
            session.add(event)
            with pytest.raises(sqlalchemy.exc.IntegrityError):
                session.commit()
            session.rollback()

        # At a trip it can only be DRIVING
        for event_type in (
            EventType.CHARGING_OPPORTUNITY,
            EventType.CHARGING_DEPOT,
            EventType.SERVICE,
            EventType.STANDBY_DEPARTURE,
            EventType.PRECONDITIONING,
        ):
            event = Event(
                scenario=session.query(Scenario).first(),
                trip=session.query(Trip).first(),
                vehicle_type=session.query(VehicleType).first(),
                event_type=event_type,
                time_start=session.query(Trip).first().departure_time,
                time_end=session.query(Trip).first().arrival_time,
            )
            session.add(event)
            with pytest.raises(sqlalchemy.exc.IntegrityError):
                session.commit()
            session.rollback()

        # TODO: Depot events are not implemented yet
        raise NotImplementedError

    @pytest.mark.skip(reason="Not implemented yet")
    def test_create_charging_depot(self, session, sample_content):
        raise NotImplementedError

    def test_create_overlapping_events_should_work(self, session, sample_content):
        # Overlapping events for the same type are allowed, since that may very well be different vehicles
        event_1 = Event(
            scenario=session.query(Scenario).first(),
            station=session.query(Station).first(),
            subloc_no=1,
            vehicle_type=session.query(VehicleType).first(),
            event_type=EventType.CHARGING_OPPORTUNITY,
            time_start=session.query(Trip).first().departure_time,
            time_end=session.query(Trip).first().arrival_time,
        )

        event_2 = Event(
            scenario=session.query(Scenario).first(),
            station=session.query(Station).first(),
            subloc_no=1,
            vehicle_type=session.query(VehicleType).first(),
            event_type=EventType.CHARGING_OPPORTUNITY,
            time_start=session.query(Trip).first().arrival_time - timedelta(minutes=10),
            time_end=session.query(Trip).first().arrival_time + timedelta(minutes=10),
        )

        session.add(event_1)
        session.add(event_2)
        session.commit()

    def test_create_overlapping_events(self, session, sample_content):
        # Overlapping events for the same type are allowed, since that may very well be different vehicles
        event_1 = Event(
            scenario=session.query(Scenario).first(),
            station=session.query(Station).first(),
            subloc_no=1,
            vehicle_type=session.query(VehicleType).first(),
            vehicle=session.query(Vehicle).first(),
            event_type=EventType.CHARGING_OPPORTUNITY,
            time_start=session.query(Trip).first().departure_time,
            time_end=session.query(Trip).first().arrival_time,
        )

        event_2 = Event(
            scenario=session.query(Scenario).first(),
            station=session.query(Station).first(),
            subloc_no=1,
            vehicle_type=session.query(VehicleType).first(),
            vehicle=session.query(Vehicle).first(),
            event_type=EventType.CHARGING_OPPORTUNITY,
            time_start=session.query(Trip).first().arrival_time - timedelta(minutes=10),
            time_end=session.query(Trip).first().arrival_time + timedelta(minutes=10),
        )

        session.add(event_1)
        session.add(event_2)

        with pytest.raises(sqlalchemy.exc.IntegrityError):
            session.commit()
        session.rollback()