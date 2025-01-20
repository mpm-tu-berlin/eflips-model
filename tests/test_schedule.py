from datetime import datetime, timedelta, timezone

import pytest
import sqlalchemy

from eflips.model import (
    AssocRouteStation,
    Line,
    Rotation,
    Route,
    Station,
    StopTime,
    Trip,
    TripType,
    VehicleType,
    ConsistencyWarning,
)
from test_general import TestGeneral


class TestTripAndStopTime(TestGeneral):
    @pytest.fixture()
    def trip(self, session, scenario):
        line = Line(name="1 - Hauptbahnhof <-> Hauptfriedhof", scenario=scenario)
        session.add(line)

        stop_1 = Station(
            name="Hauptbahnhof",
            geom="POINT(13.304398212525141 52.4995532470573 0)",
            scenario=scenario,
            is_electrified=False,
        )
        session.add(stop_1)

        stop_2 = Station(
            name="Hauptfriedhof",
            geom="POINT(13.328859958740962 52.50315841433728 0)",
            scenario=scenario,
            is_electrified=False,
        )
        session.add(stop_2)

        route = Route(
            name="1 Hauptbahnhof -> Hauptfriedhof",
            line=line,
            distance=100,
            departure_station=stop_1,
            arrival_station=stop_2,
            scenario=scenario,
        )
        session.add(route)

        vehicle_type = VehicleType(
            name="Bus",
            scenario=scenario,
            battery_capacity=100,
            charging_curve=[[0, 150], [1, 150]],
            opportunity_charging_capable=False,
            consumption=1,
        )
        session.add(vehicle_type)

        rotation = Rotation(
            scenario=scenario,
            vehicle_type=vehicle_type,
            allow_opportunity_charging=False,
        )
        session.add(rotation)

        trip = Trip(
            scenario=scenario,
            route=route,
            rotation=rotation,
            trip_type=TripType.PASSENGER,
            departure_time=datetime(
                year=2020,
                month=1,
                day=1,
                hour=12,
                minute=0,
                second=0,
                tzinfo=timezone.utc,
            ),
            arrival_time=datetime(
                year=2020,
                month=1,
                day=1,
                hour=12,
                minute=10,
                second=0,
                tzinfo=timezone.utc,
            ),
        )
        return trip

    def test_create_trip(self, session, trip):
        session.add(trip)
        session.commit()

    def test_trip_departure_microseconds(self, session, trip):
        with pytest.warns(ConsistencyWarning):
            trip.departure_time = trip.departure_time.replace(microsecond=1)
            session.add(trip)
            session.commit()

    def test_trip_arrival_microseconds(self, session, trip):
        with pytest.warns(ConsistencyWarning):
            trip.arrival_time = trip.arrival_time.replace(microsecond=999)
            session.add(trip)
            session.commit()

    def test_trip_invalid_time(self, session, trip):
        with pytest.raises(sqlalchemy.exc.IntegrityError):
            trip.departure_time = trip.arrival_time + timedelta(minutes=1)
            session.add(trip)
            session.commit()

    def test_trip_copy_scenario(self, session, trip, scenario):
        session.add(trip)
        session.commit()
        scenario_copy = scenario.clone(session)
        session.commit()

        # Check if the trip is in the copy
        assert len(scenario_copy.trips) == 1

        trip_copy = scenario_copy.trips[0]
        assert trip_copy.route.scenario == scenario_copy
        assert trip_copy.route.line.scenario == scenario_copy
        assert trip_copy.scenario == scenario_copy

    def test_stop_time(self, session, trip):
        session.add(trip)

        stop_times = []
        stop_times.append(
            StopTime(
                scenario=trip.scenario,
                trip=trip,
                station=trip.route.departure_station,
                arrival_time=trip.departure_time,
            )
        )

        intermediate_station = Station(
            name="Zwischenstation",
            geom="POINT(13.328859958740962 52.50315841433728 0)",
            scenario=trip.scenario,
            is_electrified=False,
        )

        stop_times.append(
            StopTime(
                scenario=trip.scenario,
                trip=trip,
                station=intermediate_station,
                arrival_time=trip.departure_time + timedelta(minutes=5),
            )
        )

        stop_times.append(
            StopTime(
                scenario=trip.scenario,
                trip=trip,
                station=trip.route.arrival_station,
                arrival_time=trip.arrival_time,
            )
        )
        trip.stop_times = stop_times

        session.commit()

    def test_stop_time_invalid_dwell_duration(self, session, trip):
        session.add(trip)

        stop_times = []

        stop_times.append(
            StopTime(
                scenario=trip.scenario,
                trip=trip,
                station=trip.route.departure_station,
                arrival_time=trip.departure_time,
                dwell_duration=timedelta(minutes=-11),
            )
        )

        stop_times.append(
            StopTime(
                scenario=trip.scenario,
                trip=trip,
                station=trip.route.arrival_station,
                arrival_time=trip.arrival_time,
            )
        )
        trip.stop_times = stop_times

        with pytest.raises(sqlalchemy.exc.IntegrityError):
            session.commit()

    def test_stop_time_final_stop_wrong(self, session, trip):
        session.add(trip)

        stop_times = []

        stop_times.append(
            StopTime(
                scenario=trip.scenario,
                trip=trip,
                station=trip.route.departure_station,
                arrival_time=trip.departure_time,
            )
        )

        stop_times.append(
            StopTime(
                scenario=trip.scenario,
                trip=trip,
                station=trip.route.arrival_station,
                arrival_time=trip.arrival_time - timedelta(minutes=1),
            )
        )
        trip.stop_times = stop_times

        with pytest.raises(ValueError):
            session.commit()

    def test_stop_time_first_stop_wrong(self, session, trip):
        session.add(trip)

        stop_times = []

        stop_times.append(
            StopTime(
                scenario=trip.scenario,
                trip=trip,
                station=trip.route.departure_station,
                arrival_time=trip.departure_time + timedelta(minutes=1),
                dwell_duration=timedelta(minutes=1),
            )
        )

        stop_times.append(
            StopTime(
                scenario=trip.scenario,
                trip=trip,
                station=trip.route.arrival_station,
                arrival_time=trip.arrival_time,
                dwell_duration=timedelta(minutes=1),
            )
        )

        trip.stop_times = stop_times

        with pytest.raises(ValueError):
            session.commit()

    def test_stop_time_first_stop_not_departure_station(self, session, trip):
        session.add(trip)

        station_3 = Station(
            name="Station 3",
            geom="POINT(13.328859958740962 52.50315841433728 0)",
            scenario=trip.scenario,
            is_electrified=False,
        )

        stop_times = []
        stop_times.append(
            StopTime(
                scenario=trip.scenario,
                trip=trip,
                station=station_3,
                arrival_time=trip.departure_time,
                dwell_duration=timedelta(minutes=1),
            )
        )
        stop_times.append(
            StopTime(
                scenario=trip.scenario,
                trip=trip,
                station=trip.route.departure_station,
                arrival_time=trip.departure_time,
            )
        )

        with pytest.raises(ValueError):
            trip.stop_times = stop_times
            session.commit()

    def test_stop_time_last_stop_not_arrival_station(self, session, trip):
        session.add(trip)

        station_3 = Station(
            name="Station 3",
            geom="POINT(13.328859958740962 52.50315841433728 0)",
            scenario=trip.scenario,
            is_electrified=False,
        )

        stop_times = []
        stop_times.append(
            StopTime(
                scenario=trip.scenario,
                trip=trip,
                station=trip.route.departure_station,
                arrival_time=trip.departure_time,
                dwell_duration=timedelta(minutes=1),
            )
        )
        stop_times.append(
            StopTime(
                scenario=trip.scenario,
                trip=trip,
                station=station_3,
                arrival_time=trip.arrival_time,
            )
        )

        with pytest.raises(ValueError):
            trip.stop_times = stop_times
            session.commit()

    def test_stop_time_departure_time_mismatch(self, session, trip):
        session.add(trip)

        stop_times = []

        stop_times.append(
            StopTime(
                scenario=trip.scenario,
                trip=trip,
                station=trip.route.departure_station,
                arrival_time=trip.departure_time + timedelta(minutes=10),
            )
        )

        stop_times.append(
            StopTime(
                scenario=trip.scenario,
                trip=trip,
                station=trip.route.arrival_station,
                arrival_time=trip.arrival_time,
            )
        )

        trip.stop_times = stop_times

        with pytest.raises(ValueError):
            session.commit()

    def test_stop_time_arrival_time_mismatch(self, session, trip):
        session.add(trip)

        stop_times = []

        stop_times.append(
            StopTime(
                scenario=trip.scenario,
                trip=trip,
                station=trip.route.departure_station,
                arrival_time=trip.departure_time,
            )
        )

        stop_times.append(
            StopTime(
                scenario=trip.scenario,
                trip=trip,
                station=trip.route.arrival_station,
                arrival_time=trip.arrival_time + timedelta(minutes=10),
            )
        )

        trip.stop_times = stop_times

        with pytest.raises(ValueError):
            session.commit()

    def test_stop_time_total_order_violation(self, trip, session):
        session.add(trip)

        times = (
            [
                trip.departure_time,
                trip.departure_time + timedelta(minutes=9),
                trip.departure_time + timedelta(minutes=5),
                trip.arrival_time,
            ],
            [
                trip.departure_time,
                trip.departure_time + timedelta(minutes=5),
                trip.departure_time + timedelta(minutes=9),
                trip.arrival_time,
            ],
        )

        # Add a time zone to the times
        times = [[t.replace(tzinfo=timezone.utc) for t in times[i]] for i in range(2)]

        # Create stations
        stations = []
        for i in range(4):
            stations.append(
                Station(
                    name=f"Station {i}",
                    geom=f"POINT({i} {i} 0)",
                    scenario=trip.scenario,
                    is_electrified=False,
                )
            )
        trip.route.departure_station = stations[0]
        trip.route.arrival_station = stations[3]
        session.add_all(stations)
        session.add(trip)

        # Add RouteStation associations
        for i in range(4):
            assoc = AssocRouteStation(
                scenario=trip.scenario,
                route=trip.route,
                station=stations[i],
                elapsed_distance=(trip.route.distance / 3) * i,
            )
            session.add(assoc)
        session.commit()

        for i in range(2):
            stop_times = []
            with session.no_autoflush:
                for j in range(4):
                    stop_times.append(
                        StopTime(
                            scenario=trip.scenario,
                            trip=trip,
                            station=stations[j],
                            arrival_time=times[i][j],
                        )
                    )
            if i != 1:
                with pytest.raises(ValueError):
                    trip.stop_times = stop_times
                    session.commit()
            else:
                trip.stop_times = stop_times
                session.commit()
            session.rollback()


class TestRotation(TestGeneral):
    @pytest.fixture
    def trips(self, session, scenario):
        station_1 = Station(
            name="Hauptbahnhof",
            geom="POINT(13.304398212525141 52.4995532470573 0)",
            scenario=scenario,
            is_electrified=False,
        )
        session.add(station_1)
        station_2 = Station(
            name="Hauptfriedhof",
            geom="POINT(13.328859958740962 52.50315841433728 0)",
            scenario=scenario,
            is_electrified=False,
        )
        session.add(station_2)
        route_1 = Route(
            name="1 Hauptbahnhof -> Hauptfriedhof",
            departure_station=station_1,
            arrival_station=station_2,
            distance=100,
            scenario=scenario,
        )
        session.add(route_1)
        route_2 = Route(
            name="1 Hauptfriedhof -> Hauptbahnhof",
            departure_station=station_2,
            arrival_station=station_1,
            distance=100,
            scenario=scenario,
        )
        session.add(route_2)
        line_1 = Line(name="1 - Hauptbahnhof <-> Hauptfriedhof", scenario=scenario)
        line_1.routes.append(route_1)
        session.add(line_1)

        first_departure = datetime(
            year=2020, month=1, day=1, hour=12, minute=0, second=0, tzinfo=timezone.utc
        )
        interval = timedelta(minutes=30)
        duration = timedelta(minutes=20)
        trips = []

        for i in range(15):
            # forward
            trips.append(
                Trip(
                    scenario=scenario,
                    route=route_1,
                    trip_type=TripType.PASSENGER,
                    departure_time=first_departure + 2 * i * interval,
                    arrival_time=first_departure + 2 * i * interval + duration,
                )
            )

            # backward
            trips.append(
                Trip(
                    scenario=scenario,
                    route=route_2,
                    trip_type=TripType.PASSENGER,
                    departure_time=first_departure + (2 * i + 1) * interval,
                    arrival_time=first_departure + (2 * i + 1) * interval + duration,
                )
            )

        session.add_all(trips)

        return trips

    def test_create_rotation(self, session, scenario, trips):
        session.add_all(trips)

        vehicle_type = VehicleType(
            name="Bus",
            scenario=scenario,
            battery_capacity=100,
            charging_curve=[[0, 150], [1, 150]],
            opportunity_charging_capable=False,
            consumption=1,
        )
        session.add(vehicle_type)

        rotation = Rotation(
            scenario=scenario,
            trips=trips,
            vehicle_type=vehicle_type,
            allow_opportunity_charging=False,
        )

    def test_rotation_invalid_geography(self, session, scenario, trips):
        # If we remove on trip from teh middle, a geographical discontinuity is created
        trip = trips.pop(1)
        session.expunge(trip)
        session.add_all(trips)

        vehicle_type = VehicleType(
            name="Bus",
            scenario=scenario,
            battery_capacity=100,
            charging_curve=[[0, 150], [1, 150]],
            opportunity_charging_capable=False,
            consumption=1,
        )
        session.add(vehicle_type)

        with pytest.warns(ConsistencyWarning):
            rotation = Rotation(
                scenario=scenario,
                trips=trips,
                vehicle_type=vehicle_type,
                allow_opportunity_charging=False,
            )
            session.add(rotation)
            session.commit()
        session.rollback()

    def test_rotation_invalid_time(self, session, scenario, trips):
        # Change the end time of the first trip to be beyond the start time of the second trip
        trips[0].arrival_time = trips[1].departure_time + timedelta(minutes=1)
        session.add_all(trips)

        vehicle_type = VehicleType(
            name="Bus",
            scenario=scenario,
            battery_capacity=100,
            charging_curve=[[0, 150], [1, 150]],
            opportunity_charging_capable=False,
            consumption=1,
        )
        session.add(vehicle_type)

        with pytest.warns(ConsistencyWarning):
            rotation = Rotation(
                scenario=scenario,
                trips=trips,
                vehicle_type=vehicle_type,
                allow_opportunity_charging=False,
            )
            session.add(rotation)
            session.commit()
        session.rollback()
