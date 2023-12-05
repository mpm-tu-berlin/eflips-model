from datetime import datetime, timezone

import pytest
import sqlalchemy
from sqlalchemy import func

from eflips.model import (
    AssocRouteStation,
    ChargeType,
    Line,
    Rotation,
    Route,
    Station,
    StopTime,
    Trip,
    TripType,
    VehicleType,
    VoltageLevel,
)
from test_general import TestGeneral


class TestLine(TestGeneral):
    def test_create_line(self, session, scenario):
        line = Line(name="1 - Hauptbahnhof <-> Hauptfriedhof", scenario=scenario)
        session.add(line)
        session.commit()


class TestRoute(TestGeneral):
    @pytest.fixture
    def stations(self, session, scenario):
        """Create two stations for testing."""
        station_1 = Station(
            name="Hauptbahnhof",
            geom="POINT(13.304398212525141 52.4995532470573)",
            scenario=scenario,
            is_electrified=False,
        )
        session.add(station_1)
        station_2 = Station(
            name="Hauptfriedhof",
            geom="POINT(13.328859958740962 52.50315841433728)",
            scenario=scenario,
            is_electrified=False,
        )
        session.add(station_2)

        return (station_1, station_2)

    def test_create_line_with_route(self, session, scenario, stations):
        line = Line(name="1 - Hauptbahnhof <-> Hauptfriedhof", scenario=scenario)
        session.add(line)
        session.commit()

        route = Route(
            name="1 Hauptbahnhof -> Hauptfriedhof",
            departure_station=stations[0],
            arrival_station=stations[1],
            line=line,
            distance=100,
            scenario=scenario,
        )
        session.add(route)
        session.commit()

        # Copy the scenario
        scenario_copy = scenario.clone(session)
        session.commit()

        # Check if the line is in the copy
        assert len(scenario_copy.lines) == 1
        line = scenario_copy.lines[0]
        route = line.routes[0]
        assert line.routes[0] == route

    def test_create_route_simple(self, session, scenario, stations):
        route = Route(
            name="1 Hauptbahnhof -> Hauptfriedhof",
            departure_station=stations[0],
            arrival_station=stations[1],
            distance=100,
            scenario=scenario,
        )
        session.add(route)
        session.commit()

    def test_create_route_complex(self, session, scenario, stations):
        line = Line(name="1 - Hauptbahnhof <-> Hauptfriedhof", scenario=scenario)
        session.add(line)
        session.commit()

        # Create a shape
        shape = "LINESTRINGZ(13.304398212525141 52.4995532470573 0,13.328859958740962 52.50315841433728 0)"

        route = Route(
            name="1 Hauptbahnhof -> Hauptfriedhof",
            name_short="1A",
            headsign="Hauptfriedhof",
            departure_station=stations[0],
            arrival_station=stations[1],
            line=line,
            distance=0,
            geom=shape,
            scenario=scenario,
        )
        session.add(route)

        # Use GeoAlchemy to calculate the distance
        route.distance = session.scalar(func.ST_Length(route.geom, True).select())
        session.commit()

    def test_create_route_invalid_distance(self, session, scenario, stations):
        session.add_all(stations)
        session.commit()
        distance = [-1, 0]
        for d in distance:
            with pytest.raises(sqlalchemy.exc.IntegrityError):
                route = Route(
                    scenario=scenario,
                    departure_station=stations[0],
                    arrival_station=stations[1],
                    name="1 Hauptbahnhof -> Hauptfriedhof",
                    distance=d,
                )
                session.add(route)
                session.commit()
            session.rollback()
        route = Route(
            scenario=scenario,
            departure_station=stations[0],
            arrival_station=stations[1],
            name="1 Hauptbahnhof -> Hauptfriedhof",
            distance=100,
        )
        session.add(route)
        session.commit()

    def test_route_invalid_distance(self, session, scenario, stations):
        # Create a shape
        shape = "LINESTRINGZ(13.304398212525141 52.4995532470573 0,13.328859958740962 52.50315841433728 0)"

        route = Route(
            scenario=scenario,
            departure_station=stations[0],
            arrival_station=stations[1],
            name="1 Hauptbahnhof -> Hauptfriedhof",
            distance=100,
            geom=shape,
        )

        with pytest.raises(sqlalchemy.exc.IntegrityError):
            session.add(route)
            session.commit()
        session.rollback()

        # Use GeoAlchemy to calculate the distance
        route.distance = session.scalar(func.ST_Length(route.geom, True).select())
        session.add(route)
        session.commit()

    def test_route_copy_scenario(self, session, scenario, stations):
        route = Route(
            scenario=scenario,
            departure_station=stations[0],
            arrival_station=stations[1],
            name="1 Hauptbahnhof -> Hauptfriedhof",
            distance=100,
        )
        session.add(route)
        session.commit()

        # Copy the scenario
        scenario_copy = scenario.clone(session)
        session.commit()

        # Check if the route is in the copy
        assert len(scenario_copy.routes) == 1
        route = scenario_copy.routes[0]
        assert route.departure_station.scenario == scenario_copy
        assert route.arrival_station.scenario == scenario_copy

    def test_route_stop_assoc(self, scenario, stations, session):
        route = Route(
            scenario=scenario,
            departure_station=stations[0],
            arrival_station=stations[1],
            name="1 Hauptbahnhof -> Hauptfriedhof",
            distance=100,
        )
        route.assoc_route_stations = [
            AssocRouteStation(
                scenario=scenario, station=stations[0], route=route, elapsed_distance=0
            ),
            AssocRouteStation(
                scenario=scenario,
                station=stations[1],
                route=route,
                elapsed_distance=route.distance,
            ),
        ]
        session.add(route)
        session.commit()

        assert len(route.assoc_route_stations) == 2
        assert len(route.stations) == 2

    def test_route_stop_assoc_copy(self, scenario, stations, session):
        route = Route(
            scenario=scenario,
            departure_station=stations[0],
            arrival_station=stations[1],
            name="1 Hauptbahnhof -> Hauptfriedhof",
            distance=100,
        )
        route.assoc_route_stations = [
            AssocRouteStation(
                scenario=scenario, station=stations[0], route=route, elapsed_distance=0
            ),
            AssocRouteStation(
                scenario=scenario,
                station=stations[1],
                route=route,
                elapsed_distance=route.distance,
            ),
        ]
        session.add(route)
        session.commit()

        assert len(route.assoc_route_stations) == 2
        assert len(route.stations) == 2

        # Copy the scenario
        scenario_copy = scenario.clone(session)
        session.commit()
        session.delete(scenario)
        session.commit()

        # Check if the route is in the copy
        assert len(scenario_copy.routes) == 1
        route = scenario_copy.routes[0]
        assert len(route.assoc_route_stations) == 2
        for assoc_route_station in route.assoc_route_stations:
            assert assoc_route_station.scenario == scenario_copy
            assert assoc_route_station.route == route
            assert assoc_route_station.station.scenario == scenario_copy

    def test_route_stop_assoc_missing_first_stop(self, scenario, stations, session):
        route = Route(
            scenario=scenario,
            departure_station=stations[0],
            arrival_station=stations[1],
            name="1 Hauptbahnhof -> Hauptfriedhof",
            distance=100,
        )
        with pytest.raises(ValueError):
            route.assoc_route_stations = [
                AssocRouteStation(
                    scenario=scenario,
                    station=stations[0],
                    route=route,
                    elapsed_distance=70,
                ),
                AssocRouteStation(
                    scenario=scenario,
                    station=stations[1],
                    route=route,
                    elapsed_distance=route.distance,
                ),
            ]
            session.add(route)
            session.commit()

    def test_route_stop_assoc_wrong_final_dist(self, scenario, stations, session):
        route = Route(
            scenario=scenario,
            departure_station=stations[0],
            arrival_station=stations[1],
            name="1 Hauptbahnhof -> Hauptfriedhof",
            distance=100,
        )
        with pytest.raises(ValueError):
            route.assoc_route_stations = [
                AssocRouteStation(
                    scenario=scenario,
                    station=stations[0],
                    route=route,
                    elapsed_distance=0,
                ),
                AssocRouteStation(
                    scenario=scenario,
                    station=stations[1],
                    route=route,
                    elapsed_distance=70,
                ),
            ]
            session.add(route)
            session.commit()

    def test_route_stop_assoc_wrong_first_stop(self, scenario, stations, session):
        route = Route(
            scenario=scenario,
            departure_station=stations[0],
            arrival_station=stations[1],
            name="1 Hauptbahnhof -> Hauptfriedhof",
            distance=100,
        )
        station_3 = Station(
            name="Hauptfriedhof",
            geom="POINT(13.328859958740962 52.50315841433728)",
            scenario=scenario,
            is_electrified=False,
        )
        with pytest.raises(ValueError):
            route.assoc_route_stations = [
                AssocRouteStation(
                    scenario=scenario,
                    station=station_3,
                    route=route,
                    elapsed_distance=0,
                ),
                AssocRouteStation(
                    scenario=scenario,
                    station=stations[1],
                    route=route,
                    elapsed_distance=route.distance,
                ),
            ]
            session.add(route)
            session.commit()

    def test_route_stop_assoc_wrong_last_stop(self, scenario, stations, session):
        route = Route(
            scenario=scenario,
            departure_station=stations[0],
            arrival_station=stations[1],
            name="1 Hauptbahnhof -> Hauptfriedhof",
            distance=100,
        )
        station_3 = Station(
            name="Hauptfriedhof",
            geom="POINT(13.328859958740962 52.50315841433728)",
            scenario=scenario,
            is_electrified=False,
        )
        with pytest.raises(ValueError):
            route.assoc_route_stations = [
                AssocRouteStation(
                    scenario=scenario,
                    station=stations[0],
                    route=route,
                    elapsed_distance=0,
                ),
                AssocRouteStation(
                    scenario=scenario,
                    station=station_3,
                    route=route,
                    elapsed_distance=route.distance,
                ),
            ]
            session.add(route)
            session.commit()

    def test_route_stop_assoc_wrong_order(self, scenario, stations, session):
        route = Route(
            scenario=scenario,
            departure_station=stations[0],
            arrival_station=stations[1],
            name="1 Hauptbahnhof -> Hauptfriedhof",
            distance=100,
        )
        route.assoc_route_stations = [
            AssocRouteStation(
                scenario=scenario, station=stations[0], route=route, elapsed_distance=0
            ),
            AssocRouteStation(
                scenario=scenario,
                station=stations[1],
                route=route,
                elapsed_distance=route.distance,
            ),
        ]
        session.add(route)

        vehicle_type = VehicleType(
            name="Bus",
            scenario=scenario,
            battery_capacity=100,
            charging_curve=[[0, 150], [1, 150]],
            opportunity_charging_capable=False,
        )
        session.add(vehicle_type)

        rotation = Rotation(
            scenario=scenario,
            vehicle_type=vehicle_type,
            allow_opportunity_charging=False,
        )
        session.add(rotation)

        # Create a trip
        trip = Trip(
            scenario=scenario,
            route=route,
            rotation=rotation,
            departure_time=datetime(2020, 1, 1, 12, 0, 0, tzinfo=timezone.utc),
            arrival_time=datetime(2020, 1, 1, 13, 0, 0, tzinfo=timezone.utc),
            trip_type=TripType.PASSENGER,
        )
        session.add(trip)
        session.commit()

        # Create stop times, but in the wrong order
        stop_times = [
            StopTime(
                scenario=scenario,
                trip=trip,
                station=stations[0],
                arrival_time=trip.arrival_time,
            ),
            StopTime(
                scenario=scenario,
                trip=trip,
                station=stations[1],
                arrival_time=trip.departure_time,
            ),
        ]

        with pytest.raises(ValueError):
            trip.stop_times = stop_times
            session.add(trip)
            session.commit()
        session.rollback()

        stop_times = [
            StopTime(
                scenario=scenario,
                trip=trip,
                station=stations[0],
                arrival_time=trip.departure_time,
            ),
            StopTime(
                scenario=scenario,
                trip=trip,
                station=stations[1],
                arrival_time=trip.arrival_time,
            ),
        ]
        trip.stop_times = stop_times
        session.add(trip)
        session.commit()


class TestStation(TestGeneral):
    def test_create_station(self, session, scenario):
        geom = "POINT(13.304398212525141 52.4995532470573)"

        # Create a simple station
        station = Station(
            name="Hauptbahnhof",
            geom=geom,
            scenario=scenario,
            is_electrified=False,
        )
        session.add(station)
        session.commit()

    def test_create_station_invalid_electrification(self, session, scenario):
        geom = "POINT(13.304398212525141 52.4995532470573)"
        with pytest.raises(sqlalchemy.exc.IntegrityError):
            # Create a simple station
            station = Station(
                name="Hauptbahnhof",
                geom=geom,
                scenario=scenario,
                is_electrified=True,
            )
            session.add(station)
            session.commit()
        session.rollback()
        with pytest.raises(sqlalchemy.exc.IntegrityError):
            # Create a simple station
            station = Station(
                name="Hauptbahnhof",
                geom=geom,
                scenario=scenario,
                is_electrified=False,
                power_total=100,
            )
            session.add(station)
            session.commit()

    def test_create_station_invalid_geom(self, session, scenario):
        with pytest.raises(sqlalchemy.exc.InternalError):
            # Create a simple station
            station = Station(
                name="Hauptbahnhof",
                geom=".jkdfaghjkl",
                scenario=scenario,
                is_electrified=False,
                power_total=100,
            )
            session.add(station)
            session.commit()
        session.rollback()

    def test_create_station_complete(self, session, scenario):
        geom = "POINT(13.304398212525141 52.4995532470573)"

        # Create a simple station
        station = Station(
            name="Hauptbahnhof",
            geom=geom,
            scenario=scenario,
            is_electrified=True,
            amount_charging_places=2,
            power_per_charger=22,
            power_total=44,
            charge_type=ChargeType.DEPOT,
            voltage_level=VoltageLevel.LV,
        )
        session.add(station)
        session.commit()
