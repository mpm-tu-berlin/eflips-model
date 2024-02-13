import os
from datetime import datetime, timedelta, timezone

import pytest
import sqlalchemy
from sqlalchemy import create_engine
from sqlalchemy.orm import Session

from eflips.model import (
    Area,
    AreaType,
    AssocPlanProcess,
    AssocRouteStation,
    Base,
    BatteryType,
    Depot,
    Event,
    EventType,
    Line,
    Plan,
    Process,
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
    setup_database,
)
from eflips.model.general import AssocVehicleTypeVehicleClass


class TestGeneral:
    @pytest.fixture()
    def scenario(self, session):
        """
        Creates a scenario
        :param session: An SQLAlchemy Session with the eflips-model schema
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
        :param session: An SQLAlchemy Session with the eflips-model schema
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
            opportunity_charging_capable=True,
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
            opportunity_charging_capable=True,
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
            geom="POINT(0 0 0)",
            is_electrified=False,
        )
        session.add(stop_1)

        stop_2 = Station(
            scenario=scenario,
            name="Test Station 2",
            name_short="TS2",
            geom="POINT(1 0 0)",
            is_electrified=False,
        )
        session.add(stop_2)

        stop_3 = Station(
            scenario=scenario,
            name="Test Station 3",
            name_short="TS3",
            geom="POINT(2 0 0)",
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

        area.vehicle_type = vehicle_type

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

        assocs = [
            AssocPlanProcess(scenario=scenario, process=clean, plan=plan, ordinal=1),
            AssocPlanProcess(scenario=scenario, process=charging, plan=plan, ordinal=2),
        ]
        session.add_all(assocs)

        session.commit()
        return scenario

    @pytest.fixture()
    def session(self):
        """
        Creates a session with the eflips-model schema
        NOTE: THIS DELETE ALL DATA IN THE DATABASE
        :return: an SQLAlchemy Session with the eflips-model schema
        """
        url = os.environ["DATABASE_URL"]
        engine = create_engine(
            url, echo=False
        )  # Change echo to True to see SQL queries
        Base.metadata.drop_all(engine)
        setup_database(engine)
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
        # Find the associations between plans and processes
        assoc_plan_processes = (
            session.query(AssocPlanProcess)
            .filter(AssocPlanProcess.scenario == sample_content)
            .order_by(AssocPlanProcess.ordinal)
            .all()
        )

        assert len(assoc_plan_processes) == 2
        # Remember the name of each plan and process
        plan_process_map = []
        for assoc_plan_process in assoc_plan_processes:
            plan_process_map.append(
                {
                    "plan": assoc_plan_process.plan.name,
                    "process": assoc_plan_process.process.name,
                    "ordinal": assoc_plan_process.ordinal,
                }
            )

        cloned_scenario = sample_content.clone(session)
        # Make sure that all links are also pointing back to the cloned scenario
        assert cloned_scenario.id == 2
        for vehicle_type in cloned_scenario.vehicle_types:
            assert vehicle_type.scenario == cloned_scenario
            if vehicle_type.battery_type is not None:
                assert vehicle_type.battery_type.scenario == cloned_scenario

        for battery_type in cloned_scenario.battery_types:
            assert battery_type.scenario == cloned_scenario

        # Check the plan process associations
        assoc_plan_processes = (
            session.query(AssocPlanProcess)
            .filter(AssocPlanProcess.scenario == cloned_scenario)
            .order_by(AssocPlanProcess.ordinal)
            .all()
        )

        assert len(assoc_plan_processes) == 2
        new_plan_process_map = []
        for assoc_plan_process in assoc_plan_processes:
            new_plan_process_map.append(
                {
                    "plan": assoc_plan_process.plan.name,
                    "process": assoc_plan_process.process.name,
                    "ordinal": assoc_plan_process.ordinal,
                }
            )

        assert plan_process_map == new_plan_process_map

        # Also check, that the old scenario is still intact
        # Find the associations between plans and processes
        assoc_plan_processes = (
            session.query(AssocPlanProcess)
            .filter(AssocPlanProcess.scenario == sample_content)
            .order_by(AssocPlanProcess.ordinal)
            .all()
        )

        assert len(assoc_plan_processes) == 2
        # Remember the name of each plan and process
        old_plan_process_map = []
        for assoc_plan_process in assoc_plan_processes:
            old_plan_process_map.append(
                {
                    "plan": assoc_plan_process.plan.name,
                    "process": assoc_plan_process.process.name,
                    "ordinal": assoc_plan_process.ordinal,
                }
            )
        assert plan_process_map == old_plan_process_map

        # Make sure the StopTimes are also cloned
        assert (
            session.query(StopTime).filter(StopTime.scenario == sample_content).count()
            == session.query(StopTime)
            .filter(StopTime.scenario == cloned_scenario)
            .count()
        )

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
            opportunity_charging_capable=True,
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
            opportunity_charging_capable=True,
            minimum_charging_power=10,
            length=10,
            width=10,
            height=10,
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
                    opportunity_charging_capable=True,
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
                opportunity_charging_capable=True,
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
            opportunity_charging_capable=True,
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
                    opportunity_charging_capable=True,
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
                opportunity_charging_capable=True,
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
                    opportunity_charging_capable=True,
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
            opportunity_charging_capable=True,
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
            opportunity_charging_capable=True,
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
            soc_start=0.5,
            soc_end=0.5,
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
            soc_start=0.5,
            soc_end=0.5,
        )
        session.add(event)
        session.commit()

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
                soc_start=0.5,
                soc_end=0.5,
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
                soc_start=0.5,
                soc_end=0.5,
            )
            session.add(event)
            with pytest.raises(sqlalchemy.exc.IntegrityError):
                session.commit()
            session.rollback()

        # At a depot's area it can only be CHARGING_DEPOT, SERVICE, STANDBY_DEPARTURE or PRECONDITIONING
        for event_type in (
            EventType.DRIVING,
            EventType.CHARGING_OPPORTUNITY,
        ):
            event = Event(
                scenario=session.query(Scenario).first(),
                area=session.query(Area).first(),
                vehicle_type=session.query(VehicleType).first(),
                event_type=event_type,
                time_start=session.query(Trip).first().departure_time,
                time_end=session.query(Trip).first().arrival_time,
            )
            session.add(event)
            with pytest.raises(sqlalchemy.exc.IntegrityError):
                session.commit()
            session.rollback()

    def test_create_charging_depot(self, session, sample_content):
        # Find the charging process
        charging_process = (
            session.query(Process)
            .filter(Process.electric_power > 0)
            .filter(Process.duration == None)
            .first()
        )

        event = Event(
            scenario=session.query(Scenario).first(),
            area=charging_process.areas[0],
            vehicle_type=session.query(VehicleType).first(),
            event_type=EventType.CHARGING_DEPOT,
            subloc_no=1,
            soc_start=0.5,
            soc_end=0.5,
            time_start=session.query(Trip).first().departure_time,
            time_end=session.query(Trip).first().arrival_time,
        )
        session.add(event)
        session.commit()

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
            soc_start=0.5,
            soc_end=0.5,
        )

        event_2 = Event(
            scenario=session.query(Scenario).first(),
            station=session.query(Station).first(),
            subloc_no=1,
            vehicle_type=session.query(VehicleType).first(),
            event_type=EventType.CHARGING_OPPORTUNITY,
            time_start=session.query(Trip).first().arrival_time - timedelta(minutes=10),
            time_end=session.query(Trip).first().arrival_time + timedelta(minutes=10),
            soc_start=0.5,
            soc_end=0.5,
        )

        session.add(event_1)
        session.add(event_2)
        session.commit()

    def test_create_truly_overlapping_events(self, session, sample_content):
        # Creating an event which ends after the next event starts should not be allowed
        event_1 = Event(
            scenario=session.query(Scenario).first(),
            station=session.query(Station).first(),
            subloc_no=1,
            vehicle_type=session.query(VehicleType).first(),
            vehicle=session.query(Vehicle).first(),
            event_type=EventType.CHARGING_OPPORTUNITY,
            time_start=session.query(Trip).first().departure_time,
            time_end=session.query(Trip).first().arrival_time,
            soc_start=0.5,
            soc_end=0.5,
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
            soc_start=0.5,
            soc_end=0.5,
        )

        session.add(event_1)
        session.add(event_2)

        with pytest.raises(sqlalchemy.exc.IntegrityError):
            session.commit()
        session.rollback()

        # Also create an event wholly contained within another event
        event_1 = Event(
            scenario=session.query(Scenario).first(),
            station=session.query(Station).first(),
            subloc_no=1,
            vehicle_type=session.query(VehicleType).first(),
            vehicle=session.query(Vehicle).first(),
            event_type=EventType.CHARGING_OPPORTUNITY,
            time_start=session.query(Trip).first().departure_time,
            time_end=session.query(Trip).first().arrival_time,
            soc_start=0.5,
            soc_end=0.5,
        )

        event_2 = Event(
            scenario=session.query(Scenario).first(),
            station=session.query(Station).first(),
            subloc_no=1,
            vehicle_type=session.query(VehicleType).first(),
            vehicle=session.query(Vehicle).first(),
            event_type=EventType.CHARGING_OPPORTUNITY,
            time_start=session.query(Trip).first().departure_time
            + timedelta(minutes=1),
            time_end=session.query(Trip).first().arrival_time - timedelta(minutes=1),
            soc_start=0.5,
            soc_end=0.5,
        )

        session.add(event_1)
        session.add(event_2)

        with pytest.raises(sqlalchemy.exc.IntegrityError):
            session.commit()
        session.rollback()

    def test_create_overlapping_events(self, session, sample_content):
        # Creating an event with its start time being exactly the same as the end time of another event should not be allowed
        event_1 = Event(
            scenario=session.query(Scenario).first(),
            station=session.query(Station).first(),
            subloc_no=1,
            vehicle_type=session.query(VehicleType).first(),
            vehicle=session.query(Vehicle).first(),
            event_type=EventType.CHARGING_OPPORTUNITY,
            time_start=session.query(Trip).first().departure_time,
            time_end=session.query(Trip).first().arrival_time,
            soc_start=0.5,
            soc_end=0.5,
        )

        event_2 = Event(
            scenario=session.query(Scenario).first(),
            station=session.query(Station).first(),
            subloc_no=1,
            vehicle_type=session.query(VehicleType).first(),
            vehicle=session.query(Vehicle).first(),
            event_type=EventType.CHARGING_OPPORTUNITY,
            time_start=session.query(Trip).first().arrival_time,
            time_end=session.query(Trip).first().arrival_time + timedelta(minutes=10),
            soc_start=0.5,
            soc_end=0.5,
        )

        session.add(event_1)
        session.add(event_2)
        session.commit()

        # Howeever, if we move the end of the first event forward by even one microsecond, it should not be allowed
        event_3 = Event(
            scenario=session.query(Scenario).first(),
            station=session.query(Station).first(),
            subloc_no=1,
            vehicle_type=session.query(VehicleType).first(),
            vehicle=session.query(Vehicle).first(),
            event_type=EventType.CHARGING_OPPORTUNITY,
            time_start=session.query(Trip).first().departure_time,
            time_end=session.query(Trip).first().arrival_time
            + timedelta(microseconds=1),
            soc_start=0.5,
            soc_end=0.5,
        )

        event_4 = Event(
            scenario=session.query(Scenario).first(),
            station=session.query(Station).first(),
            subloc_no=1,
            vehicle_type=session.query(VehicleType).first(),
            vehicle=session.query(Vehicle).first(),
            event_type=EventType.CHARGING_OPPORTUNITY,
            time_start=session.query(Trip).first().arrival_time,
            time_end=session.query(Trip).first().arrival_time + timedelta(minutes=10),
            soc_start=0.5,
            soc_end=0.5,
        )

        session.add(event_3)
        session.add(event_4)
        with pytest.raises(sqlalchemy.exc.IntegrityError):
            session.commit()

    def test_create_negative_event(self, session, sample_content):
        # An event with a negative duration should not be allowed
        event_1 = Event(
            scenario=session.query(Scenario).first(),
            station=session.query(Station).first(),
            subloc_no=1,
            vehicle_type=session.query(VehicleType).first(),
            vehicle=session.query(Vehicle).first(),
            event_type=EventType.CHARGING_OPPORTUNITY,
            time_start=session.query(Trip).first().arrival_time,
            time_end=session.query(Trip).first().departure_time,
            soc_start=0.5,
            soc_end=0.5,
        )
        session.add(event_1)
        with pytest.raises(sqlalchemy.exc.IntegrityError):
            session.commit()

    def test_create_zero_event(self, session, sample_content):
        # An event with a negative duration should not be allowed
        event_1 = Event(
            scenario=session.query(Scenario).first(),
            station=session.query(Station).first(),
            subloc_no=1,
            vehicle_type=session.query(VehicleType).first(),
            vehicle=session.query(Vehicle).first(),
            event_type=EventType.CHARGING_OPPORTUNITY,
            time_start=session.query(Trip).first().arrival_time,
            time_end=session.query(Trip).first().arrival_time,
            soc_start=0.5,
            soc_end=0.5,
        )
        session.add(event_1)
        with pytest.raises(sqlalchemy.exc.IntegrityError):
            session.commit()
