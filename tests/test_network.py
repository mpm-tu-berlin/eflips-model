import pytest
import sqlalchemy
from sqlalchemy import func

from eflips.model import Line, Route, Station, ChargeType, VoltageLevel
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
