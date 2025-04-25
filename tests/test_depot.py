from datetime import timedelta

import pytest
import sqlalchemy
from matplotlib import pyplot as plt
from sqlalchemy.exc import IntegrityError
import geoalchemy2.shape as ga_shape
from shapely.geometry import Polygon, Point, box
from geoalchemy2 import Geometry
import math

from eflips.model import (
    Area,
    AreaType,
    Depot,
    Plan,
    Process,
    Scenario,
    VehicleType,
    AssocPlanProcess,
    Station,
)
from tests.test_general import TestGeneral


class TestDepot(TestGeneral):
    @pytest.fixture()
    def depot_with_content(self, session, scenario):
        # Create a simple depot
        station = Station(
            scenario=scenario,
            name="Test Station 1",
            name_short="TS1",
            geom="POINT(0 0 0)",
            is_electrified=False,
        )
        session.add(station)

        depot = Depot(
            scenario=scenario, name="Test Depot", name_short="TD", station=station
        )
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
            capacity=6,
            row_count=1,
        )
        session.add(area)

        # Create vehicle type for area
        test_vehicle_type = VehicleType(
            scenario=scenario,
            name="Test Vehicle Type 2",
            battery_capacity=100,
            charging_curve=[[0, 150], [1, 150]],
            opportunity_charging_capable=True,
            consumption=1,
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

        plan.asssoc_plan_process.append(
            AssocPlanProcess(scenario=scenario, process=clean, plan=plan, ordinal=1)
        )
        plan.asssoc_plan_process.append(
            AssocPlanProcess(scenario=scenario, process=charging, plan=plan, ordinal=2)
        )

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
            consumption=1,
        )

        line_area = Area(
            scenario=scenario,
            depot=depot_with_content,
            name="line area",
            area_type=AreaType.LINE,
            capacity=6,
            row_count=1,
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
            name="Test Process  number 2",
            scenario=scenario,
            dispatchable=False,
            duration=timedelta(minutes=30),
        )

        session.add(process)
        session.commit()

        process = Process(
            name="Test Process number 3",
            scenario=scenario,
            dispatchable=False,
            electric_power=150,
        )
        session.add(process)
        session.commit()

        # test invalid process with negative duration and power
        with pytest.raises(sqlalchemy.exc.IntegrityError):
            process = Process(
                name="Test Process number 4",
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
        plan.asssoc_plan_process.append(
            AssocPlanProcess(scenario=scenario, process=process, plan=plan, ordinal=1)
        )
        session.commit()

        assert process.plans == [plan]


class TestGeography(TestGeneral):
    """Tests for the geographical features of depots and areas."""

    @pytest.fixture()
    def depot_with_geography(self, session, scenario):
        """Create a depot with a bounding box."""
        # Create a station
        station = Station(
            scenario=scenario,
            name="Geo Station",
            name_short="GS",
            geom="POINT(13.4050 52.5200 0)",  # Berlin coordinates
            is_electrified=False,
        )
        session.add(station)

        # Create a depot with a bounding box (rectangular area around Berlin)
        depot = Depot(
            scenario=scenario, name="Geo Depot", name_short="GD", station=station
        )

        # Create a bounding box polygon for the depot
        # Simple rectangle around the station
        depot_poly = box(13.40, 52.51, 13.41, 52.52)

        # Convert to PostGIS format
        depot.bounding_box = ga_shape.from_shape(depot_poly, srid=4326)

        session.add(depot)

        # Create plan for the depot
        plan = Plan(scenario=scenario, name="Geo Plan")
        session.add(plan)
        depot.default_plan = plan

        # Create area
        vehicle_type = VehicleType(
            scenario=scenario,
            name="Test Bus",
            battery_capacity=100,
            charging_curve=[[0, 150], [1, 150]],
            opportunity_charging_capable=True,
            consumption=1,
            length=12.0,  # 12 meter bus
            width=2.5,  # 2.5 meter wide
            height=3.5,  # 3.5 meter high
        )
        session.add(vehicle_type)

        vehicle_type_2 = VehicleType(
            scenario=scenario,
            name="Test Truck",
            battery_capacity=200,
            charging_curve=[[0, 150], [1, 150]],
            opportunity_charging_capable=True,
            consumption=2,
            length=18.0,  # 18 meter truck
            width=3.0,  # 3.0 meter wide
            height=4.0,  # 4.0 meter high
        )
        session.add(vehicle_type_2)

        area = Area(
            scenario=scenario,
            name="Geo Area",
            depot=depot,
            area_type=AreaType.LINE,
            capacity=36,
            row_count=6,
            vehicle_type=vehicle_type,
        )
        session.add(area)

        area_2 = Area(
            scenario=scenario,
            name="Geo Area 2",
            depot=depot,
            area_type=AreaType.LINE,
            vehicle_type=vehicle_type_2,
            capacity=18,
            row_count=3,
        )
        session.add(area_2)

        # Cerate a direct-oneside area
        direct_oneside_area = Area(
            scenario=scenario,
            name="Direct One Side Area",
            depot=depot,
            area_type=AreaType.DIRECT_ONESIDE,
            capacity=12,
            row_count=None,
            vehicle_type=vehicle_type,
        )
        session.add(direct_oneside_area)

        # ANother one-side area for long bois
        direct_oneside_area_2 = Area(
            scenario=scenario,
            name="Direct One Side Area 2",
            depot=depot,
            area_type=AreaType.DIRECT_ONESIDE,
            capacity=12,
            row_count=None,
            vehicle_type=vehicle_type_2,
        )
        session.add(direct_oneside_area_2)

        session.commit()

        return depot

    def test_depot_bounding_box(self, session, depot_with_geography):
        """Test that depot bounding box properties work correctly."""
        # Get the depot from the database
        depot = depot_with_geography

        # Test bounding box creation
        assert depot.bounding_box is not None

        # Test global bounding box accessor
        global_poly = depot.bounding_box_global
        assert global_poly is not None
        assert global_poly.is_valid
        assert global_poly.area > 0

        # Test validation
        assert depot.validate_bounding_box() is True

    def test_coordinate_transformations(self, session, depot_with_geography):
        """Test coordinate system transformations."""
        depot = depot_with_geography

        # Get the global polygon
        global_poly = depot.bounding_box_global

        # Transform to local
        local_poly = depot.global_to_local(global_poly)
        assert local_poly is not None

        # Transform back to global and compare with original
        back_to_global = depot.local_to_global(local_poly)
        assert back_to_global is not None

        # The polygons should be approximately the same
        # Use symmetric difference to compare (should be very small)
        sym_diff = global_poly.symmetric_difference(back_to_global)
        assert sym_diff.area / global_poly.area < 0.01  # < 1% difference

        # Create a point in global coordinates and transform
        global_point = Point(13.4050, 52.5200)  # Point in Berlin

        # Test transformation of arbitrary point
        projection_data = depot.local_projection
        assert projection_data is not None

        _, to_local, _ = projection_data
        local_coords = to_local.transform(global_point.x, global_point.y)

        # Local coordinates should be in meters
        assert isinstance(local_coords[0], float)
        assert isinstance(local_coords[1], float)

        # Local origin should be near the center of the bounding box
        # (Since we're using a Transverse Mercator projection centered at the centroid)
        centroid = global_poly.centroid
        centroid_local = to_local.transform(centroid.x, centroid.y)

        # The centroid in local coords should be near (0,0)
        assert abs(centroid_local[0]) < 1000  # Within 1km of the origin
        assert abs(centroid_local[1]) < 1000  # Within 1km of the origin

    def test_area_bounding_box(self, session, depot_with_geography):
        """Test setting and getting area bounding boxes."""
        depot = depot_with_geography

        # Get the depot's bounding box in local coordinates to find suitable origins
        depot_local = depot.bounding_box_local
        assert depot_local is not None

        # Get the minimum corner of the depot's bounding box
        minx, miny, maxx, maxy = depot_local.bounds

        # Set bounding boxes for all areas with different positions and angles
        for i, area in enumerate(depot.areas):
            # Use different origin points for each area to avoid overlaps
            # Add spacing based on the area index
            spacing = 20  # meters between areas
            origin = Point(minx + 10 + (i * spacing * 2), miny + 10 + (i * spacing))

            # Alternate between 0 and 45 degree angles
            angle = 0 if i % 2 == 0 else math.pi / 4

            # Set the bounding box
            area.set_bounding_box_from_local(origin, angle=angle)

            # Verify the bounding box was created
            assert area.bounding_box is not None

            # Test the area's bounding box in global and local coordinates
            global_poly = area.bounding_box_global
            assert global_poly is not None

            local_poly = area.bounding_box_local
            assert local_poly is not None

            # Test validation
            assert area.validate_bounding_box() is True

    def test_svg_generation(self, session, depot_with_geography):
        """Test SVG generation for depot."""
        depot = depot_with_geography

        # Make sure all areas have a bounding box
        depot_local = depot.bounding_box_local
        minx, miny, maxx, maxy = depot_local.bounds

        for i, area in enumerate(depot.areas):
            if area.bounding_box is None:
                # Use different origin points for each area
                spacing = 20  # meters between areas
                origin = Point(minx + 10 + (i * spacing * 2), miny + 10 + (i * spacing))
                angle = 0 if i % 2 == 0 else math.pi / 4
                area.set_bounding_box_from_local(origin, angle=angle)

        # Generate SVG
        svg_string = depot.generate_svg()

        # TODO: REMOVE THIS
        # save to file
        with open("test.svg", "w") as f:
            f.write(svg_string)

        # Basic checks on SVG content
        assert svg_string is not None
        assert len(svg_string) > 0
        assert "<svg" in svg_string
        assert "</svg>" in svg_string

        # Check that depot name is in the SVG
        assert depot.name in svg_string

        # Check that all area names are in the SVG
        for area in depot.areas:
            assert area.name in svg_string

        # Test with different parameters
        svg_string = depot.generate_svg(
            margin=20.0, vehicle_opacity=0.5, draw_vehicles=False
        )
        assert svg_string is not None
        assert len(svg_string) > 0

    def test_area_constraints(self, session, depot_with_geography):
        """Test area constraints for bounding boxes."""
        depot = depot_with_geography

        # Create an area with a bounding box outside the depot (should fail)
        vehicle_type = depot.areas[0].vehicle_type

        outside_area = Area(
            scenario=depot.scenario,
            name="Outside Area",
            depot=depot,
            area_type=AreaType.LINE,
            capacity=6,
            row_count=2,
            vehicle_type=vehicle_type,
        )
        session.add(outside_area)

        # Create a polygon outside the depot's bounding box
        depot_global = depot.bounding_box_global
        minx, miny, maxx, maxy = depot_global.bounds

        # Create a polygon 1 degree away (way outside the depot)
        outside_poly = box(minx - 1, miny - 1, minx - 0.9, miny - 0.9)

        # This should not violate any constraints yet since there's no bounding box
        session.commit()

        # Add the bounding box - this should fail when committed due to constraints
        outside_area.bounding_box = ga_shape.from_shape(outside_poly, srid=4326)

        # Validate should return false
        assert outside_area.validate_bounding_box() is False

        # Committing should fail due to constraints
        with pytest.raises(IntegrityError):
            session.commit()

        # Rollback the session
        session.rollback()

        # Test with a non-rectangular polygon (triangle)
        triangle_area = Area(
            scenario=depot.scenario,
            name="Triangle Area",
            depot=depot,
            area_type=AreaType.LINE,
            capacity=6,
            row_count=2,
            vehicle_type=vehicle_type,
        )
        session.add(triangle_area)

        # Create a triangle inside the depot's bounding box
        depot_local = depot.bounding_box_local
        minx, miny, maxx, maxy = depot_local.bounds

        # Create a triangle in local coordinates
        triangle = Polygon(
            [
                (minx + 10, miny + 10),
                (minx + 20, miny + 10),
                (minx + 15, miny + 20),
            ]
        )

        # Transform to global coordinates
        triangle_global = depot.local_to_global(triangle)

        # Add the bounding box - this should fail when committed due to rectangular constraint
        triangle_area.bounding_box = ga_shape.from_shape(triangle_global, srid=4326)

        # Validate should return false
        assert triangle_area.validate_bounding_box() is False

        # Committing should fail due to constraints
        with pytest.raises(IntegrityError):
            session.commit()

        session.rollback()

        # Test a valid area inside the depot's bounding box
        valid_area = Area(
            scenario=depot.scenario,
            name="Valid Test Area",
            depot=depot,
            area_type=AreaType.DIRECT_TWOSIDE,
            capacity=10,
            vehicle_type=vehicle_type,
        )
        session.add(valid_area)

        # Create a valid rectangle inside the depot's bounding box
        # Find a position not used by existing areas
        depot_local = depot.bounding_box_local
        minx, miny, maxx, maxy = depot_local.bounds

        # Position at the center of the depot
        center_x = (minx + maxx) / 2
        center_y = (miny + maxy) / 2
        origin = Point(center_x, center_y)

        # Set a valid bounding box
        valid_area.set_bounding_box_from_local(origin, angle=math.pi / 6)  # 30 degrees

        # Validate should return true
        assert valid_area.validate_bounding_box() is True

        # Commit should succeed
        session.commit()

        # Check that the valid area has a bounding box
        assert valid_area.bounding_box is not None
        assert valid_area.bounding_box_global is not None
        assert valid_area.bounding_box_local is not None

    def test_generate_parking_spaces(self, session, depot_with_geography):
        """Test generation of parking spaces within areas."""
        depot = depot_with_geography

        # Make sure all areas have a bounding box
        depot_local = depot.bounding_box_local
        minx, miny, maxx, maxy = depot_local.bounds

        for i, area in enumerate(depot.areas):
            if area.bounding_box is None:
                # Use different origin points for each area
                spacing = 20  # meters between areas
                origin = Point(minx + 10 + (i * spacing * 2), miny + 10 + (i * spacing))
                angle = 0 if i % 2 == 0 else math.pi / 6
                area.set_bounding_box_from_local(origin, angle=angle)

        # Test generation of parking spaces for each area
        for area in depot.areas:
            parking_spaces = area.generate_parking_spaces()

            # Basic checks
            assert parking_spaces is not None
            assert len(parking_spaces) == area.capacity

            # Check that all parking spaces are within the area's bounding box
            area_polygon = area.bounding_box_local
            for space in parking_spaces:
                # Check that each space is valid
                assert space.is_valid
                assert space.area > 0

                # Check that space is within the area with small tolerance
                # We use a small buffer to account for floating point precision
                # assert space.within(area_polygon.buffer(0.01)) TODO

                # Check the dimensions are approximately correct
                # For simple rectangular spaces, the area should be approximately vehicle length * width
                if area.area_type == AreaType.LINE:
                    # Allow 5% tolerance for dimensions
                    expected_area = area.vehicle_type.length * area.vehicle_type.width
                    assert abs(space.area - expected_area) / expected_area < 0.05

        # Test visualization method
        for area in depot.areas:
            # This should generate a figure and not raise any exceptions
            fig = area.visualize_parking_spaces()
            plt.axis("equal")
            plt.show()
            assert fig is not None
