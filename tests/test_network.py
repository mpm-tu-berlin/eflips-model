from datetime import datetime, timedelta

import pytest
import sqlalchemy
from sqlalchemy import func

from eflips.model import ChargeType, Line, Route, Station, Trip, TripType, VoltageLevel
from test_general import TestGeneral


class TestLine(TestGeneral):
    def test_create_line(self, session, scenario):
        line = Line(name="1 - Hauptbahnhof <-> Hauptfriedhof", scenario=scenario)
        session.add(line)
        session.commit()

    def test_create_line_with_route(self, session, scenario):
        line = Line(name="1 - Hauptbahnhof <-> Hauptfriedhof", scenario=scenario)
        session.add(line)
        session.commit()
        route = Route(
            name="1 Hauptbahnhof -> Hauptfriedhof",
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


class TestRoute(TestGeneral):
    def test_create_route_simple(self, session, scenario):
        route = Route(
            name="1 Hauptbahnhof -> Hauptfriedhof", distance=100, scenario=scenario
        )
        session.add(route)
        session.commit()

    def test_create_route_complex(self, session, scenario):
        line = Line(name="1 - Hauptbahnhof <-> Hauptfriedhof", scenario=scenario)
        session.add(line)
        session.commit()

        # Create a shape
        shape = "LINESTRING(13.304398212525141 52.4995532470573,13.328859958740962 52.50315841433728)"

        route = Route(
            name="1 Hauptbahnhof -> Hauptfriedhof",
            name_short="1A",
            headsign="Hauptfriedhof",
            line=line,
            distance=0,
            shape=shape,
            scenario=scenario,
        )
        session.add(route)

        # Use GeoAlchemy to calculate the distance
        route.distance = session.scalar(func.ST_Length(route.shape, True).select())
        session.commit()


class TestStation(TestGeneral):
    def test_create_station(self, session, scenario):
        location = "POINT(13.304398212525141 52.4995532470573)"

        # Create a simple station
        station = Station(
            name="Hauptbahnhof",
            location=location,
            scenario=scenario,
            is_electrified=False,
        )
        session.add(station)
        session.commit()

    def test_create_station_invalid_electrification(self, session, scenario):
        location = "POINT(13.304398212525141 52.4995532470573)"
        with pytest.raises(sqlalchemy.exc.IntegrityError):
            # Create a simple station
            station = Station(
                name="Hauptbahnhof",
                location=location,
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
                location=location,
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
                location=".jkdfaghjkl",
                scenario=scenario,
                is_electrified=False,
                power_total=100,
            )
            session.add(station)
            session.commit()
        session.rollback()

    def test_create_station_complete(self, session, scenario):
        location = "POINT(13.304398212525141 52.4995532470573)"

        # Create a simple station
        station = Station(
            name="Hauptbahnhof",
            location=location,
            scenario=scenario,
            is_electrified=True,
            amount_charging_poles=2,
            power_per_charger=22,
            power_total=44,
            charge_type=ChargeType.DEPOT,
            voltage_level=VoltageLevel.LV,
        )
        session.add(station)
        session.commit()


class TestTrip(TestGeneral):
    @pytest.fixture()
    def trip(self, session, scenario):
        line = Line(name="1 - Hauptbahnhof <-> Hauptfriedhof", scenario=scenario)
        session.add(line)

        route = Route(
            name="1 Hauptbahnhof -> Hauptfriedhof",
            line=line,
            distance=100,
            scenario=scenario,
        )
        session.add(route)

        stop_1 = Station(
            name="Hauptbahnhof",
            location="POINT(13.304398212525141 52.4995532470573)",
            scenario=scenario,
            is_electrified=False,
        )
        session.add(stop_1)

        stop_2 = Station(
            name="Hauptfriedhof",
            location="POINT(13.328859958740962 52.50315841433728)",
            scenario=scenario,
            is_electrified=False,
        )
        session.add(stop_2)

        trip = Trip(
            scenario=scenario,
            route=route,
            departure_station=stop_1,
            arrival_station=stop_2,
            trip_type=TripType.PASSENGER,
            departure_time=datetime(
                year=2020, month=1, day=1, hour=12, minute=0, second=0
            ),
            arrival_time=datetime(
                year=2020, month=1, day=1, hour=12, minute=10, second=0
            ),
        )
        return trip

    def test_create_trip(self, session, trip):
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
        assert trip_copy.departure_station.scenario == scenario_copy
        assert trip_copy.arrival_station.scenario == scenario_copy
        assert trip_copy.scenario == scenario_copy
