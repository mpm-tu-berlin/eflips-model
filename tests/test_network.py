from datetime import datetime, timezone

import geoalchemy2
import pytest
import sqlalchemy
from geoalchemy2 import WKTElement, Geometry
from geoalchemy2.shape import from_shape, to_shape
from sqlalchemy import func, text

from eflips.model import (
    AssocRouteStation,
    ChargeType,
    Line,
    Block,
    Route,
    Station,
    StopTime,
    Trip,
    TripType,
    VehicleType,
    VoltageLevel,
    ChargingPointType,
)
from test_general import TestGeneral
import shapely.wkt


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
            geom=self.wkt_for_coordinates(1, 0, 0),
            scenario=scenario,
            is_electrified=False,
        )
        session.add(station_1)
        station_2 = Station(
            name="Hauptfriedhof",
            geom=self.wkt_for_coordinates(2, 0, 0),
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

        session.commit()
        route = Route(
            name="1 Hauptbahnhof -> Hauptfriedhof",
            name_short="1A",
            headsign="Hauptfriedhof",
            departure_station=stations[0],
            arrival_station=stations[1],
            line=line,
            distance=Route.calculate_length(session, shape),
            geom=shape,
            scenario=scenario,
        )

        session.add(route)
        session.commit()

        # Check if the route was created correctly
        session.expire(route)

        # Assert that the geometry is correct
        from_db = to_shape(route.geom)
        assert from_db is not None

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
        route.distance = Route.calculate_length(session, shape)
        assert route.distance > 0
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
            geom=self.wkt_for_coordinates(1, 0, 0),
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
            geom=self.wkt_for_coordinates(2, 0, 0),
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
            consumption=1,
        )
        session.add(vehicle_type)

        block = Block(
            scenario=scenario,
            vehicle_type=vehicle_type,
            allow_opportunity_charging=False,
        )
        session.add(block)

        # Create a trip
        trip = Trip(
            scenario=scenario,
            route=route,
            block=block,
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
        # Create a simple station
        station = Station(
            name="Hauptbahnhof",
            geom=self.wkt_for_coordinates(1, 0, 0),
            scenario=scenario,
            is_electrified=False,
        )
        session.add(station)
        session.commit()

    def test_create_station_invalid_electrification(self, session, scenario):
        with pytest.raises(sqlalchemy.exc.IntegrityError):
            # Create a simple station
            station = Station(
                name="Hauptbahnhof",
                geom=self.wkt_for_coordinates(1, 0, 0),
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
                geom=self.wkt_for_coordinates(1, 0, 0),
                scenario=scenario,
                is_electrified=False,
                power_total=100,
            )
            session.add(station)
            session.commit()

    def test_create_station_invalid_geom(self, session, scenario):
        if session.bind.dialect.name == "sqlite":
            with pytest.raises(ValueError):
                # Create a simple station
                station = Station(
                    name="Hauptbahnhof",
                    geom=".jkdfaghjkl",
                    scenario=scenario,
                    is_electrified=False,
                    power_total=None,
                )
                session.add(station)
                session.commit()
        else:
            with pytest.raises(sqlalchemy.exc.InternalError):
                # Create a simple station
                station = Station(
                    name="Hauptbahnhof",
                    geom=".jkdfaghjkl",
                    scenario=scenario,
                    is_electrified=False,
                    power_total=None,
                )
                session.add(station)
                session.commit()
        session.rollback()

    def test_create_station_complete(self, session, scenario):
        lat = 52.5162607
        lon = 13.3321242
        alt = 0
        wkt = self.wkt_for_coordinates(lon, lat, alt)
        # Create a simple station
        station = Station(
            name="Hauptbahnhof",
            geom=wkt,
            scenario=scenario,
            is_electrified=True,
            amount_charging_places=2,
            power_per_charger=22,
            power_total=44,
            charge_type=ChargeType.DEPOT,
            voltage_level=VoltageLevel.LV,
            tco_parameters={
                "procurement": 500000.0,
                "lifetime": 20,
                "cost_escalation": 0.02,
            },
        )
        session.add(station)

        charging_point_type = ChargingPointType(
            scenario=scenario,
            name="Hauptbahnhof",
            tco_parameters={
                "procurement": 500000.0,
                "lifetime": 20,
                "cost_escalation": 0.02,
            },
        )
        session.add(charging_point_type)
        station.charging_point_type = charging_point_type

        session.commit()

        session.expire(station)

        # Assure that the "geom" attribute still works
        # Create a shapely geometry from station.geom
        from_db = to_shape(station.geom)
        assert from_db.x == lon
        assert from_db.y == lat
        assert from_db.z == alt
