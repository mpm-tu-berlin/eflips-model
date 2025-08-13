from datetime import datetime, timedelta
from enum import auto, Enum as PyEnum
from math import sin, cos, sqrt, radians, degrees, atan2
from typing import List, Tuple, TYPE_CHECKING, Optional, Dict, Any

import geoalchemy2.shape as ga_shape
from geoalchemy2 import Geometry
from pyproj import Transformer, CRS
from shapely import affinity  # type: ignore[import-untyped]
from shapely.geometry import Polygon as ShapelyPolygon, Point, box  # type: ignore[import-untyped]
from sqlalchemy import (
    BigInteger,
    Boolean,
    CheckConstraint,
    Enum as SqlEnum,
    Float,
    ForeignKey,
    Integer,
    Interval,
    Text,
    UniqueConstraint,
    Constraint,
    JSON,
    event,
)
from sqlalchemy.dialects import postgresql
from sqlalchemy.orm import Mapped, mapped_column, relationship

from eflips.model import Base

if TYPE_CHECKING:
    from eflips.model import Scenario, VehicleType, Event, Station, ChargingPointType


class Depot(Base):
    """
    The Depot represents a palce where vehicles not engaged in a schedule are parked,
    processed and dispatched.
    """

    __tablename__ = "Depot"
    id: Mapped[int] = mapped_column(
        BigInteger().with_variant(Integer, "sqlite"), primary_key=True
    )
    """The unique idenfitier of the depot. Auto-incremented."""

    scenario_id: Mapped[int] = mapped_column(ForeignKey("Scenario.id"))
    """The unique identifier of the scenario. Foreign key to :attr:`Scenario.id`."""
    scenario: Mapped["Scenario"] = relationship("Scenario", back_populates="depots")
    """The scenario this depot belongs to."""

    name: Mapped[str] = mapped_column(Text)
    """A name for the depot."""
    name_short: Mapped[str] = mapped_column(Text, nullable=True)
    """An optional short name for the depot."""
    bounding_box = mapped_column(Geometry("POLYGON", srid=4326), nullable=True)
    """The bounding box of the depot as a PostGIS Polygon. Uses WGS84 coordinate system (SRID 4326)."""

    station_id: Mapped[int] = mapped_column(ForeignKey("Station.id"))
    """The station where the depot is located. This depot handles :attr:`Rotation` starting and ending at this station. Foreign key to :attr:`Station.id`."""
    station: Mapped["Station"] = relationship("Station", back_populates="depot")
    """The station where the depot is located. This depot handles :attr:`Rotation` starting and ending at this station."""

    default_plan_id: Mapped[int] = mapped_column(ForeignKey("Plan.id"))
    """The default plan of this depot. Foreign key to :attr:`Plan.id`."""
    default_plan: Mapped["Plan"] = relationship("Plan", back_populates="depot")

    areas: Mapped[List["Area"]] = relationship("Area", back_populates="depot")
    """The areas of this depot."""

    __table_args__ = (
        # What we actually would like is have station_id globally unique, but this raises
        # a violation during the step of copyying wheer the data is duplicated already but the relationships
        # are not yet updated. So we have to live with the unique constraint on the scenario level.
        UniqueConstraint(scenario_id, station_id),
        # Ensure the bounding box is valid if it exists
        CheckConstraint(
            "(bounding_box IS NULL) OR "
            "(ST_IsValid(bounding_box) AND ST_Area(bounding_box) > 0)",
            name="depot_bounding_box_valid_check",
        ),
    )

    def __repr__(self) -> str:
        return f"<Depot(id={self.id}, name={self.name})>"

    @property
    def local_projection(self) -> Optional[Tuple[CRS, Transformer, Transformer]]:
        """
        Creates a local metric coordinate system centered at the centroid of the depot's bounding box.

        Returns:
            A tuple containing:
            - The pyproj CRS object for the local projection
            - Transformer from WGS84 to local
            - Transformer from local to WGS84
            Returns None if no bounding box is defined.
        """
        if self.bounding_box is None:
            return None

        # Convert the GeoAlchemy2 geometry to a shapely geometry
        geom = ga_shape.to_shape(self.bounding_box)

        # Get the centroid of the polygon
        centroid = geom.centroid
        lon, lat = centroid.x, centroid.y

        # Create a local metric projection centered at the depot's centroid
        # Using a Transverse Mercator projection for local accuracy
        proj_string = f"+proj=tmerc +lat_0={lat} +lon_0={lon} +k=1 +x_0=0 +y_0=0 +ellps=WGS84 +units=m +no_defs"
        local_crs = CRS.from_proj4(proj_string)

        # Create transformers in both directions
        wgs84 = CRS.from_epsg(4326)
        to_local = Transformer.from_crs(wgs84, local_crs, always_xy=True)
        to_global = Transformer.from_crs(local_crs, wgs84, always_xy=True)

        return (local_crs, to_local, to_global)

    def global_to_local(self, polygon: ShapelyPolygon) -> Optional[ShapelyPolygon]:
        """
        Converts a shapely polygon from the global WGS84 coordinate system to the depot's local coordinate system.

        Args:
            polygon: A shapely polygon in WGS84 coordinates (EPSG:4326)

        Returns:
            A shapely polygon with coordinates in the local metric system, or None if no bounding box is defined.
        """
        projection_data = self.local_projection
        if projection_data is None:
            return None

        _, transformer, _ = projection_data

        # Transform coordinates
        exterior_coords = list(polygon.exterior.coords)
        transformed_exterior = [transformer.transform(x, y) for x, y in exterior_coords]

        # Handle interior rings (holes) if any
        transformed_interiors = []
        for interior in polygon.interiors:
            interior_coords = list(interior.coords)
            transformed_interior = [
                transformer.transform(x, y) for x, y in interior_coords
            ]
            transformed_interiors.append(transformed_interior)

        # Create new polygon with transformed coordinates
        return ShapelyPolygon(transformed_exterior, transformed_interiors)

    def local_to_global(self, polygon: ShapelyPolygon) -> Optional[ShapelyPolygon]:
        """
        Converts a shapely polygon from the depot's local coordinate system to the global WGS84 coordinate system.

        Args:
            polygon: A shapely polygon in the depot's local metric coordinates

        Returns:
            A shapely polygon with coordinates in WGS84 (EPSG:4326), or None if no bounding box is defined.
        """
        projection_data = self.local_projection
        if projection_data is None:
            return None

        _, _, transformer = projection_data

        # Transform coordinates
        exterior_coords = list(polygon.exterior.coords)
        transformed_exterior = [transformer.transform(x, y) for x, y in exterior_coords]

        # Handle interior rings (holes) if any
        transformed_interiors = []
        for interior in polygon.interiors:
            interior_coords = list(interior.coords)
            transformed_interior = [
                transformer.transform(x, y) for x, y in interior_coords
            ]
            transformed_interiors.append(transformed_interior)

        # Create new polygon with transformed coordinates
        return ShapelyPolygon(transformed_exterior, transformed_interiors)

    @property
    def bounding_box_global(self) -> Optional[ShapelyPolygon]:
        """
        Returns the bounding box of the area as a shapely Polygon.

        Returns:
            A shapely Polygon representing the bounding box in WGS84 coordinates, or None if no bounding box is defined.
        """
        if self.bounding_box is None:
            return None

        return ga_shape.to_shape(self.bounding_box)

    @property
    def bounding_box_local(self) -> Optional[ShapelyPolygon]:
        """
        Returns the bounding box of the area in the depot's local coordinate system.

        Returns:
            A shapely Polygon with coordinates in the local metric system, or None if no bounding box is defined.
        """
        global_polygon = self.bounding_box_global
        if global_polygon is None or self.bounding_box is None:
            return None

        return self.global_to_local(global_polygon)

    def validate_bounding_box(self) -> bool:
        """
        Validates that the depot's bounding box is valid.

        Returns:
            True if the bounding box is valid or None, False otherwise.
        """
        if self.bounding_box is None:
            return True

        # Convert to shapely to perform validation
        poly = self.bounding_box_global

        # Check if polygon is valid and has positive area
        return poly is not None and poly.is_valid and poly.area > 0

    def generate_svg(
        self,
        width: int = 800,
        height: int = 800,
        margin: int = 20,
        draw_labels: bool = True,
        draw_area_info: bool = True,
        draw_parking_spaces: bool = True,
    ) -> str:
        """
        Generates an SVG visualization of the depot, including areas and parking spaces.

        **NOTE: This method requires the `svgwrite` library to be installed.**

        Args:
            width: The width of the SVG in pixels
            height: The height of the SVG in pixels
            margin: Margin around the depot in pixels
            draw_labels: Whether to draw labels for areas and parking spaces
            draw_area_info: Whether to draw information about each area
            draw_parking_spaces: Whether to draw individual parking spaces

        Returns:
            The SVG as a string

        :raise ImportError: If svgwrite is not installed
        """
        try:
            import svgwrite.container  # type: ignore[import-untyped]
            import svgwrite.shapes  # type: ignore[import-untyped]
        except ImportError:
            raise ImportError(
                "svgwrite is not installed. Please install it to use this feature."
            )

        # Check if the depot has a bounding box
        if self.bounding_box is None:
            return f'<svg width="{width}" height="{height}" xmlns="http://www.w3.org/2000/svg"><text x="10" y="30" font-size="16">No bounding box defined for depot</text></svg>'

        # Get the depot's bounding box in local coordinates
        depot_bbox = self.bounding_box_local
        if depot_bbox is None:
            return f'<svg width="{width}" height="{height}" xmlns="http://www.w3.org/2000/svg"><text x="10" y="30" font-size="16">Error getting local bounding box</text></svg>'

        # Get bounds of the depot's bounding box
        min_x, min_y, max_x, max_y = depot_bbox.bounds

        # Calculate scaling factors to fit the depot in the SVG with margins
        bbox_width = max_x - min_x
        bbox_height = max_y - min_y

        # Calculate scaling factor preserving aspect ratio
        scale_x = (width - 2 * margin) / bbox_width
        scale_y = (height - 2 * margin) / bbox_height
        scale = min(scale_x, scale_y)

        # SVG uses top-left as origin, so we need to flip Y coordinates
        # Transform function: local coords to SVG coords
        def transform_point(x: float, y: float) -> Tuple[float, float]:
            # Apply scaling and translation to fit in SVG, and flip Y coordinate
            svg_x = margin + (x - min_x) * scale
            # Flip Y-axis (SVG has Y increasing downward)
            svg_y = height - margin - (y - min_y) * scale
            return svg_x, svg_y

        # Transform a polygon to SVG coordinates
        def transform_polygon(polygon: ShapelyPolygon) -> List[Tuple[float, float]]:
            exterior_coords = list(polygon.exterior.coords)
            transformed_coords = [transform_point(x, y) for x, y in exterior_coords]
            return transformed_coords

        # Create SVG drawing
        dwg = svgwrite.Drawing(profile="tiny", size=(width, height))

        # Create a group for the depot
        depot_group = svgwrite.container.Group(id="depot")

        # Draw depot bounding box
        depot_outline = transform_polygon(depot_bbox)
        depot_polygon = svgwrite.shapes.Polygon(
            depot_outline, fill="none", stroke="black", stroke_width=2
        )
        depot_group.add(depot_polygon)

        # Add depot name
        if draw_labels:
            center_x = margin + bbox_width * scale / 2
            depot_group.add(
                dwg.text(
                    self.name,
                    insert=(center_x, margin / 2),
                    text_anchor="middle",
                    font_size=16,
                    font_weight="bold",
                )
            )

        # Group for all areas
        areas_group = svgwrite.container.Group(id="areas")

        # Dictionary to map vehicle types to colors
        # We'll create a deterministic color mapping based on vehicle type ID
        vehicle_type_colors: Dict[int, str] = {}
        # List of distinct colors for different vehicle types
        distinct_colors = [
            "#4285F4",  # Google Blue
            "#EA4335",  # Google Red
            "#FBBC05",  # Google Yellow
            "#34A853",  # Google Green
            "#9C27B0",  # Purple
            "#00BCD4",  # Cyan
            "#FF9800",  # Orange
            "#795548",  # Brown
            "#607D8B",  # Blue Grey
            "#E91E63",  # Pink
        ]

        # Draw each area
        for i, area in enumerate(self.areas):
            # Get area bounding box
            area_bbox = area.bounding_box_local
            if area_bbox is None:
                continue

            # Create group for this area
            area_group = svgwrite.container.Group(id=f"area_{area.id}")

            # Determine fill color based on vehicle type
            fill_color = "#CCCCCC"  # Default gray if no vehicle type
            if area.vehicle_type:
                # If we haven't seen this vehicle type before, assign a color
                if area.vehicle_type.id not in vehicle_type_colors:
                    color_index = len(vehicle_type_colors) % len(distinct_colors)
                    vehicle_type_colors[area.vehicle_type.id] = distinct_colors[
                        color_index
                    ]
                fill_color = vehicle_type_colors[area.vehicle_type.id]

            # Draw area bounding box
            area_outline = transform_polygon(area_bbox)
            area_polygon = svgwrite.shapes.Polygon(
                area_outline,
                fill=fill_color,
                stroke="black",
                stroke_width=1,
                fill_opacity=0.5,
            )
            area_group.add(area_polygon)

            # Add area name if available
            if draw_labels and area.name:
                # Get center of the area
                centroid = area_bbox.centroid
                center_x, center_y = transform_point(centroid.x, centroid.y)

                # Add area name
                area_group.add(
                    dwg.text(
                        area.name,
                        insert=(center_x, center_y),
                        text_anchor="middle",
                        font_size=12,
                        font_weight="bold",
                    )
                )

            # Add area information
            if draw_area_info:
                min_x_area, min_y_area, max_x_area, max_y_area = area_bbox.bounds
                info_x, info_y = transform_point(min_x_area, max_y_area)

                # Create background rectangle for info text
                info_bg = dwg.rect(
                    insert=(
                        info_x,
                        info_y - 75,
                    ),  # Increased height for vehicle type info
                    size=(150, 75),  # Increased height
                    fill="white",
                    stroke="black",
                    stroke_width=0.5,
                    opacity=0.8,
                    rx=3,
                    ry=3,
                )
                area_group.add(info_bg)

                # Add area type, capacity, row count, and vehicle type if applicable
                info_text = []
                info_text.append(f"Type: {area.area_type.name}")
                info_text.append(f"Capacity: {area.capacity}")

                if area.area_type == AreaType.LINE and area.row_count:
                    info_text.append(f"Rows: {area.row_count}")

                # Add vehicle type information
                if area.vehicle_type:
                    info_text.append(f"Vehicle: {area.vehicle_type.name}")
                    if area.vehicle_type.length and area.vehicle_type.width:
                        info_text.append(
                            f"Size: {area.vehicle_type.length:.1f}m × {area.vehicle_type.width:.1f}m"
                        )

                for idx, text in enumerate(info_text):
                    area_group.add(
                        dwg.text(
                            text,
                            insert=(info_x + 5, info_y - 60 + idx * 15),
                            font_size=10,
                        )
                    )

            # Draw parking spaces if requested
            if draw_parking_spaces:
                parking_spaces = area.generate_parking_spaces()
                if parking_spaces:
                    # Create a group for parking spaces
                    spaces_group = svgwrite.container.Group(id=f"spaces_area_{area.id}")

                    # Draw each parking space
                    for j, space in enumerate(parking_spaces):
                        space_outline = transform_polygon(space)
                        space_polygon = svgwrite.shapes.Polygon(
                            space_outline, fill="none", stroke="blue", stroke_width=0.5
                        )
                        spaces_group.add(space_polygon)

                        # Add space number if requested and not too many spaces
                        if draw_labels and area.capacity <= 50:
                            centroid = space.centroid
                            space_x, space_y = transform_point(centroid.x, centroid.y)
                            spaces_group.add(
                                dwg.text(
                                    str(j + 1),
                                    insert=(space_x, space_y),
                                    text_anchor="middle",
                                    font_size=6,
                                )
                            )

                    area_group.add(spaces_group)

            # Add this area group to the areas group
            areas_group.add(area_group)

        # Add all groups to the drawing
        depot_group.add(areas_group)
        dwg.add(depot_group)

        dwg_string = dwg.tostring()

        assert isinstance(dwg_string, str), "SVG string is not a valid string"

        return dwg_string


class Plan(Base):
    """
    The Plan represents a certain order of processes, which are executed on vehicles in a depot.
    """

    __tablename__ = "Plan"

    id: Mapped[int] = mapped_column(
        BigInteger().with_variant(Integer, "sqlite"), primary_key=True
    )
    """The unique identifier of the plan. Auto-incremented."""

    scenario_id: Mapped[int] = mapped_column(ForeignKey("Scenario.id"))
    """The unique identifier of the scenario. Foreign key to :attr:`Scenario.id`."""
    scenario: Mapped["Scenario"] = relationship("Scenario", back_populates="plans")
    """The scenario this plan belongs to."""

    name: Mapped[str] = mapped_column(Text)
    """A name for the plan."""

    depot: Mapped["Depot"] = relationship("Depot", back_populates="default_plan")

    asssoc_plan_process: Mapped[List["AssocPlanProcess"]] = relationship(
        "AssocPlanProcess",
        back_populates="plan",
        order_by="AssocPlanProcess.ordinal",
    )
    """The association between this plan and its processes. Here, the ordinal of the process can be set."""

    processes: Mapped[List["Process"]] = relationship(
        "Process",
        secondary="AssocPlanProcess",
        back_populates="plans",
        order_by="AssocPlanProcess.ordinal",
        viewonly=True,
    )

    def __repr__(self) -> str:
        return f"<Plan(id={self.id}, name={self.name})>"


class AreaType(PyEnum):
    """This class represents the type of area in eFLIPS-Depot"""

    DIRECT_ONESIDE = auto()
    """A direct area where vehicles drive in form one side only."""

    DIRECT_TWOSIDE = auto()
    """A direct area where vehicles drive in form both sides. Also called a "herringbone" configuration."""

    LINE = auto()
    """A line area where vehicles are parked in a line. There might be one or more rows in the area."""


class Area(Base):
    """
    An Area represents a certain area in a depot, where at least one process is available.

    All slots in the area may be directly accessible, or the area may be a line area where vehicles are parked in a
    line. In such an area, only the first vehicle in the line is directly accessible, the second vehicle can only be
    removed after the first vehicle has been removed, and so on. However vehicles can only been added to the end of the
    line. So if it's filled up, *all* vehicles have to be removed to add a new one. If there's one slot left and one
    vehicle is removed, there's still only one slot left, not two.

    """

    __tablename__ = "Area"

    _table_args_list: List[Constraint] = []

    id: Mapped[int] = mapped_column(
        BigInteger().with_variant(Integer, "sqlite"), primary_key=True
    )
    """The unique identifier of the area. Auto-incremented."""

    scenario_id: Mapped[int] = mapped_column(ForeignKey("Scenario.id"))
    """The unique identifier of the scenario. Foreign key to :attr:`Scenario.id`."""
    scenario: Mapped["Scenario"] = relationship("Scenario", back_populates="areas")
    """The scenario this area belongs to."""

    depot_id: Mapped[int] = mapped_column(ForeignKey("Depot.id"))
    """The unique identifier of the depot. Foreign key to :attr:`Depot.id`."""
    depot: Mapped["Depot"] = relationship("Depot", back_populates="areas")

    vehicle_type_id: Mapped[int] = mapped_column(
        ForeignKey("VehicleType.id"), nullable=True
    )
    """The unique identifier of the vehicle type. Foreign key to :attr:`VehicleType.id`.
    If set, only vehicles of this type can be parked in this area. If null, all vehicle types can be parked."""
    vehicle_type: Mapped["VehicleType"] = relationship(
        "VehicleType", back_populates="areas"
    )
    """The vehicle type which can park in this area."""

    area_type = mapped_column(SqlEnum(AreaType, native_enum=False))
    """The type of the area. See :class:`depot.AreaType`."""

    name: Mapped[str] = mapped_column(Text, nullable=True)
    """An optional name for the area. If set, it must be unique within the scenario."""

    name_short: Mapped[str] = mapped_column(Text, nullable=True)
    """An optional short name for the area."""

    capacity: Mapped[int] = mapped_column(Integer)
    """The capacity of the area. Must be set."""

    row_count: Mapped[int] = mapped_column(Integer, nullable=True)
    """Number of side-by-side rows in a LINE area. Must be set for areas of type LINE."""

    charging_point_type_id: Mapped[int] = mapped_column(
        ForeignKey("ChargingPointType.id"), nullable=True
    )
    """If this is a charging area, this is the type of charging point. Used for TCO/LCA calculations."""

    charging_point_type: Mapped["ChargingPointType"] = relationship(
        "ChargingPointType", back_populates="areas"
    )
    """The type of charging point in this area."""

    bounding_box = mapped_column(Geometry("POLYGON", srid=4326), nullable=True)
    """The bounding box of the area as a PostGIS Polygon. Uses WGS84 coordinate system (SRID 4326)."""

    capacity_constraint = CheckConstraint(
        "capacity > 0 AND "
        "((area_type = 'DIRECT_TWOSIDE' AND row_count IS NULL AND capacity % 2 = 0) "
        "OR (area_type = 'DIRECT_ONESIDE' AND row_count IS NULL) "
        "OR (area_type = 'LINE' AND row_count IS NOT NULL AND capacity % row_count = 0))",
        name="capacity_validity_check",
    )

    # Constraint to ensure area bounding box is rectangular
    # For a polygon to be a rectangle, it must have exactly 4 points (plus closing point)
    # This is a more reliable check than using ST_Envelope which only works for axis-aligned rectangles
    rectangular_constraint = CheckConstraint(
        "(bounding_box IS NULL) OR "
        "(ST_Area(bounding_box) > 0 AND "
        "ST_NPoints(ST_ExteriorRing(bounding_box)) = 5)",
        name="area_rectangular_check",
    )

    processes: Mapped[List["Process"]] = relationship(
        "Process", secondary="AssocAreaProcess", back_populates="areas"
    )

    events: Mapped[List["Event"]] = relationship("Event", back_populates="area")
    """The events that happened in this area."""

    assoc_area_processes: Mapped[List["AssocAreaProcess"]] = relationship(
        "AssocAreaProcess", viewonly=True
    )
    """The association between this area and its processes."""

    _table_args_list.append(capacity_constraint)
    _table_args_list.append(rectangular_constraint)

    __table_args__ = tuple(_table_args_list)

    spacing = 0.5
    """The spacing between vehicles when parked, in meters."""
    direct_area_angle = radians(45)
    """The angle of the direct area, in radians."""

    @property
    def length(self) -> None | float:
        """
        Calculates the length of the area. For a line area, this is the vehicles behind each other in a row.
        for a direct area, this is the length of the side that needs to have road access.
        """

        # We cannot calculate the size if the vehicle type is not set
        if self.vehicle_type is None:
            return None

        vehicle_length = self.vehicle_type.length
        vehicle_width = self.vehicle_type.width

        if self.direct_area_angle != radians(45):
            raise ValueError("Changing the angle might mess up the")

        if self.area_type == AreaType.LINE:
            vehicles_per_row = self.capacity // self.row_count
            assert vehicles_per_row == int(vehicles_per_row)

            # The length is the length of the vehicle plus the spacing between the vehicles
            # But without the spacing at the end of the row
            return vehicles_per_row * self.spacing + vehicles_per_row * vehicle_length
        elif self.area_type == AreaType.DIRECT_ONESIDE:
            # For angled parking, the length needs to account for the full projection
            # of each vehicle along the baseline, plus spacing between them
            angle = self.direct_area_angle

            # Calculate how far apart each vehicle needs to be
            stagger_distance = 2 * vehicle_width * cos(angle) + self.spacing

            # The total length is the stagger distance times the number of vehicles
            # plus an extra half spacing at each end
            return (
                (self.capacity - 0.5) * stagger_distance
                + self.spacing
                + sin(angle) * vehicle_length
            )
        elif self.area_type == AreaType.DIRECT_TWOSIDE:
            raise NotImplementedError("Not implemented")
        else:
            return None

    @property
    def width(self) -> None | float:
        """
        Calculates the width of the area. For a line area, this is the width of the side that needs to have road access.
        """
        if self.vehicle_type is None:
            return None

        if self.area_type == AreaType.LINE:
            effective_width = self.vehicle_type.width + self.spacing
            return effective_width * self.row_count
        elif self.area_type == AreaType.DIRECT_ONESIDE:
            # For angled parking, width needs to account for the full projection
            # of the vehicle perpendicular to the baseline
            vehicle_length = self.vehicle_type.length
            vehicle_width = self.vehicle_type.width
            angle = self.direct_area_angle

            # The width is the depth of the parking spaces plus spacing
            return (
                vehicle_length * cos(angle) + vehicle_width * sin(angle) + self.spacing
            )
        elif self.area_type == AreaType.DIRECT_TWOSIDE:
            raise NotImplementedError("Not implemented")
        else:
            return None

    def _coordinates(self) -> None | Tuple[float, float, float]:
        """
        Gets the x, and y coordinates of the area's first point in the local coordinate system.
        Also returns the angle of the area in the local coordinate system.

        :return: A tuple containing the x, y coordinates and the angle of the area in the local coordinate system.
        """
        if self.bounding_box_local is None:
            return None

        # Get the bounding box in local coordinates
        bbox = self.bounding_box_local

        # Extract the coordinates of the bounding box
        # Note: shapely returns coordinates as [(x0,y0), (x1,y1), ..., (x0,y0)] with the second-to-last point
        # being the same as the original first point
        origin = list(bbox.exterior.coords)[-2]

        x = origin[0]
        y = origin[1]

        # THe angle is between the origin (second-to-last point) and the last point
        last_point = list(bbox.exterior.coords)[-1]
        dx = last_point[0] - origin[0]
        dy = last_point[1] - origin[1]
        alpha = atan2(dy, dx)

        return x, y, alpha

    @property
    def x(self) -> Optional[float]:
        """
        Represents the X (East (+) - West (-)) coordinate of the area in the depot's local coordinate system.
        This is the coordinate of the first corner of the area in the local coordinate system.
        :return: A float representing the X coordinate of the area in the local coordinate system.
        """
        result = self._coordinates()
        if result is None:
            return None
        else:
            x, _, _ = result
            return x

    @property
    def y(self) -> Optional[float]:
        """
        Represents the Y (North (+) - South (-)) coordinate of the area in the depot's local coordinate system.
        This is the coordinate of the bottom left corner of the area in the local coordinate system.
        :return: A float representing the Y coordinate of the area in the local coordinate system.
        """
        result = self._coordinates()
        if result is None:
            return None
        else:
            _, y, _ = result
            return y

    @property
    def alpha(self) -> Optional[float]:
        """
        Represents the angle of the area in the depot's local coordinate system.
        This is the angle of the bottom left edge of the area in the local coordinate system.
        :return: A float representing the angle of the area in the local coordinate system, in radians.
        """
        result = self._coordinates()
        if result is None:
            return None
        else:
            _, _, alpha = result
            return alpha

    def __repr__(self) -> str:
        return f"<Area(id={self.id}, name={self.name}, area_type={self.area_type}, capacity={self.capacity})>"

    def set_bounding_box_from_local(self, origin: Point, angle: float) -> None:
        """
        Sets the bounding box of the area based on a rectangle defined by:
        - An origin point in the local coordinate system
        - An angle in radians for the orientation of the rectangle
        - The width and length properties of the area

        Args:
            origin: A shapely Point in the local coordinate system representing the origin corner
            angle: The angle in radians for the orientation of the rectangle

        Returns:
            None

        Raises:
            ValueError: If width or length properties return None, or if the depot has no bounding box
        """
        if self.length is None or self.width is None:
            raise ValueError(
                "Cannot set bounding box: Area length or width is not available"
            )

        if self.depot.bounding_box is None:
            raise ValueError(
                "Cannot set bounding box: Depot has no bounding box defined"
            )

        # Get the dimensions of the area
        length = self.length
        width = self.width

        # COORDINATE SYSTEM FIX:
        # When creating a box in spatial coordinates, be explicit about the orientation
        # In spatial coordinates, typically:
        # - X increases to the east (right)
        # - Y increases to the north (up)
        #
        # Create an unrotated rectangle with the origin at the bottom-left
        # The length extends along the X-axis, the width extends along the Y-axis
        unrotated_box = box(
            origin.x,  # minx
            origin.y,  # miny
            origin.x + length,  # maxx
            origin.y + width,  # maxy
        )

        # Rotate the rectangle around the origin using affine transformation
        # The rotation angle in shapely.affinity.rotate is counterclockwise in degrees
        angle_degrees = degrees(angle)  # Convert radians to degrees
        rotated_box = affinity.rotate(
            unrotated_box, angle_degrees, origin=(origin.x, origin.y)
        )

        # Transform to global coordinates using the depot's transformation
        global_polygon = self.depot.local_to_global(rotated_box)
        if global_polygon is None:
            raise ValueError("Failed to transform polygon to global coordinates")

        # Store as PostGIS geometry
        self.bounding_box = ga_shape.from_shape(global_polygon, srid=4326)

    @property
    def bounding_box_global(self) -> Optional[ShapelyPolygon]:
        """
        Returns the bounding box of the area as a shapely Polygon.

        Returns:
            A shapely Polygon representing the bounding box in WGS84 coordinates, or None if no bounding box is defined.
        """
        if self.bounding_box is None:
            return None

        return ga_shape.to_shape(self.bounding_box)

    @property
    def bounding_box_local(self) -> Optional[ShapelyPolygon]:
        """
        Returns the bounding box of the area in the depot's local coordinate system.

        Returns:
            A shapely Polygon with coordinates in the local metric system, or None if no bounding box is defined.
        """
        global_polygon = self.bounding_box_global
        if global_polygon is None or self.depot.bounding_box is None:
            return None

        return self.depot.global_to_local(global_polygon)

    def generate_parking_spaces(self) -> Optional[List[ShapelyPolygon]]:
        """
        Generates polygons representing the individual parking spaces within the area.

        Returns:
            A list of shapely Polygons representing each parking space in local coordinates,
            or None if the area has no bounding box or vehicle type defined.
        """
        if self.bounding_box_local is None or self.vehicle_type is None:
            return None

        vehicle_length = self.vehicle_type.length
        vehicle_width = self.vehicle_type.width

        # Get the bounding box in local coordinates
        bbox = self.bounding_box_local

        # Extract the coordinates of the bounding box
        # Note: shapely returns coordinates as [(x0,y0), (x1,y1), ..., (x0,y0)] with the last point repeating the first
        bbox_coords = list(bbox.exterior.coords)[:-1]  # Exclude the repeated point

        if len(bbox_coords) != 4:
            # Not a valid rectangle
            return None

        parking_spaces = []

        # Calculate the two edge vectors of the bounding box for a local coordinate system
        # These vectors will be used as the basis for our local coordinates
        vec1 = (
            bbox_coords[1][0] - bbox_coords[0][0],
            bbox_coords[1][1] - bbox_coords[0][1],
        )
        vec2 = (
            bbox_coords[3][0] - bbox_coords[0][0],
            bbox_coords[3][1] - bbox_coords[0][1],
        )

        # Calculate lengths of the edges
        len1 = sqrt(vec1[0] ** 2 + vec1[1] ** 2)
        len2 = sqrt(vec2[0] ** 2 + vec2[1] ** 2)

        # Normalize vectors to get unit vectors for the local coordinate system
        unit_vec1 = (vec1[0] / len1, vec1[1] / len1)
        unit_vec2 = (vec2[0] / len2, vec2[1] / len2)

        # Origin point for the local coordinate system
        origin = bbox_coords[0]

        if self.area_type == AreaType.LINE:
            # For line areas, vehicles are parked in rows
            vehicles_per_row = self.capacity // self.row_count

            # Calculate the size of each parking space
            space_length = vehicle_length
            space_width = vehicle_width

            # Choose which edge corresponds to rows and which to columns
            # Use the semantic width and length of the area rather than just picking the longer edge

            # Find which edge vector is more aligned with the width and which with the length
            # We do this by checking which edge is more closely aligned with each dimension
            area_length = self.length
            area_width = self.width

            if area_length is None or area_width is None:
                # Fall back to using the longer edge for rows if semantic dimensions are unavailable
                if len1 > len2:
                    row_vector = unit_vec1
                    col_vector = unit_vec2
                    row_length = len1
                    col_length = len2
                else:
                    row_vector = unit_vec2
                    col_vector = unit_vec1
                    row_length = len2
                    col_length = len1
            else:
                # Calculate which bounding box edge better corresponds to the semantic length
                # by checking which is closer to the proper aspect ratio
                ratio1 = len1 / len2
                ratio2 = len2 / len1
                area_ratio = area_length / area_width

                # If ratio1 is closer to area_ratio than ratio2 is to area_ratio,
                # then vec1 corresponds to length and vec2 to width
                if abs(ratio1 - area_ratio) < abs(ratio2 - area_ratio):
                    row_vector = unit_vec1  # Length direction
                    col_vector = unit_vec2  # Width direction
                    row_length = len1
                    col_length = len2
                else:
                    row_vector = unit_vec2  # Length direction
                    col_vector = unit_vec1  # Width direction
                    row_length = len2
                    col_length = len1

            # Calculate how many vehicles can fit along each vector
            for row in range(self.row_count):
                for col in range(vehicles_per_row):
                    # Calculate position in the local coordinate system
                    # Add half spacing to initial position for balanced spacing on both sides
                    offset_x = col * (space_length + self.spacing) + self.spacing / 2
                    offset_y = row * (space_width + self.spacing) + self.spacing / 2

                    # Convert to the bounding box coordinate system
                    # This calculates a point that is offset_x along row_vector and offset_y along col_vector
                    # from the origin of the bounding box
                    corner_x = (
                        origin[0] + offset_x * row_vector[0] + offset_y * col_vector[0]
                    )
                    corner_y = (
                        origin[1] + offset_x * row_vector[1] + offset_y * col_vector[1]
                    )

                    # Calculate the four corners of the parking space
                    p1 = (corner_x, corner_y)
                    p2 = (
                        corner_x + space_length * row_vector[0],
                        corner_y + space_length * row_vector[1],
                    )
                    p3 = (
                        p2[0] + space_width * col_vector[0],
                        p2[1] + space_width * col_vector[1],
                    )
                    p4 = (
                        corner_x + space_width * col_vector[0],
                        corner_y + space_width * col_vector[1],
                    )

                    # Create the polygon and add it to the list
                    space = ShapelyPolygon([p1, p2, p3, p4])
                    parking_spaces.append(space)

        elif self.area_type == AreaType.DIRECT_ONESIDE:
            # For direct one-side areas, vehicles are parked at an angle (herringbone pattern)
            angle = self.direct_area_angle  # In radians, should be 45 degrees (π/4)

            # Calculate the effective dimensions for each parking space
            vehicle_length = self.vehicle_type.length
            vehicle_width = self.vehicle_type.width

            # In a herringbone pattern, we need to determine the longest edge of the bounding box
            # This will be our baseline for positioning the vehicles
            if len1 > len2:
                # First edge is longer - use it as the baseline
                baseline_vector = unit_vec1
                perp_vector = unit_vec2
                baseline_length = len1
                perp_length = len2
            else:
                # Second edge is longer - use it as the baseline
                baseline_vector = unit_vec2
                perp_vector = unit_vec1
                baseline_length = len2
                perp_length = len1

            # Calculate how far apart each vehicle should be along the baseline
            # For angled parking, we need to account for the full projection of the vehicle
            # onto the baseline to avoid overlap
            stagger_distance = 2 * vehicle_width * cos(angle) + self.spacing

            # Calculate how deep the parking spaces extend from the baseline
            # This depends on both the length and width of the vehicle at the given angle
            depth = vehicle_length * cos(angle) + vehicle_width * sin(angle)

            # Calculate the offset needed from the corner of the bounding box to ensure
            # no part of the parking spaces extends beyond the bounding box
            # For a 45-degree angle, the most extreme point is vehicle_width projected at that angle
            offset_from_corner = vehicle_width * cos(angle)

            # For a herringbone pattern with 45 degree angle:
            # Each space is a rectangle rotated 45 degrees from the baseline
            parking_spaces = []

            # Starting position - add offset to ensure spaces stay within bounds,
            # plus half spacing for balance between spaces
            # Also add sin(angle) × spacing to move further inside the area
            start_pos_x = (
                origin[0]
                + (offset_from_corner + sin(angle) * self.spacing) * perp_vector[0]
                + self.spacing / 2 * baseline_vector[0]
            )
            start_pos_y = (
                origin[1]
                + (offset_from_corner + sin(angle) * self.spacing) * perp_vector[1]
                + self.spacing / 2 * baseline_vector[1]
            )

            for i in range(self.capacity):
                # Calculate the position along the baseline for this vehicle
                pos_x = start_pos_x + i * stagger_distance * baseline_vector[0]
                pos_y = start_pos_y + i * stagger_distance * baseline_vector[1]

                # Define the four corners of the parking space
                # For 45-degree angled parking, we need to adjust the corner calculations

                # The first point is offset from the baseline
                p1 = (pos_x, pos_y)

                # The second point is along the rotated width direction
                p2_x = (
                    pos_x
                    + vehicle_width * cos(angle) * baseline_vector[0]
                    - vehicle_width * sin(angle) * perp_vector[0]
                )
                p2_y = (
                    pos_y
                    + vehicle_width * cos(angle) * baseline_vector[1]
                    - vehicle_width * sin(angle) * perp_vector[1]
                )

                # The third point adds the vehicle length in the perpendicular direction
                p3_x = (
                    p2_x
                    + vehicle_length * sin(angle) * baseline_vector[0]
                    + vehicle_length * cos(angle) * perp_vector[0]
                )
                p3_y = (
                    p2_y
                    + vehicle_length * sin(angle) * baseline_vector[1]
                    + vehicle_length * cos(angle) * perp_vector[1]
                )

                # The fourth point is vehicle length from the first point in the perpendicular direction
                p4_x = (
                    pos_x
                    + vehicle_length * sin(angle) * baseline_vector[0]
                    + vehicle_length * cos(angle) * perp_vector[0]
                )
                p4_y = (
                    pos_y
                    + vehicle_length * sin(angle) * baseline_vector[1]
                    + vehicle_length * cos(angle) * perp_vector[1]
                )

                # Create the polygon
                space = ShapelyPolygon(
                    [(p1[0], p1[1]), (p2_x, p2_y), (p3_x, p3_y), (p4_x, p4_y)]
                )
                parking_spaces.append(space)

        elif self.area_type == AreaType.DIRECT_TWOSIDE:
            raise NotImplementedError("Not implemented")

        return parking_spaces

    def validate_bounding_box(self) -> bool:
        """
        Validates that the area's bounding box is valid:
        - Must be rectangular (4 vertices forming right angles)
        - Must be within the depot's bounding box
        - Must have positive area

        Returns:
            True if the bounding box meets all constraints or is None, False otherwise.
        """
        if self.bounding_box is None:
            return True

        # Check if depot has a bounding box
        if self.depot.bounding_box is None:
            return False

        # Get polygons in shapely format
        area_poly = self.bounding_box_local
        depot_poly = self.depot.bounding_box_local

        if area_poly is None or depot_poly is None:
            return False

        # Check if area is within depot
        if not area_poly.within(depot_poly):
            return False

        # Check if area has positive area
        if area_poly.area <= 0:
            return False

        # Check if area is rectangular
        # A true rectangle has exactly 4 vertices (plus the closing vertex which is the same as the first)
        # and all internal angles should be 90 degrees (π/2 radians)

        # Get coordinates excluding the closing vertex
        coords = list(area_poly.exterior.coords)[:-1]

        # Check vertex count - must be exactly 4 for a rectangle
        if len(coords) != 4:
            return False

        # Calculate vectors between consecutive vertices
        vectors = []
        for i in range(4):
            next_i = (i + 1) % 4
            vector = (
                coords[next_i][0] - coords[i][0],
                coords[next_i][1] - coords[i][1],
            )
            # Normalize vector
            length = (vector[0] ** 2 + vector[1] ** 2) ** 0.5
            if length > 0:
                vectors.append((vector[0] / length, vector[1] / length))
            else:
                # Zero-length vector - degenerate polygon
                return False

        # Check for right angles - dot product of adjacent vectors should be close to 0
        for i in range(4):
            next_i = (i + 1) % 4
            dot_product = (
                vectors[i][0] * vectors[next_i][0] + vectors[i][1] * vectors[next_i][1]
            )
            # Allow for floating point precision issues
            if abs(dot_product) > 0.01:  # Not perpendicular
                return False

        return True


class Process(Base):
    """A Process represents a certain action that can be executed on a vehicle."""

    __tablename__ = "Process"

    _table_args_list: List[Constraint] = []

    id: Mapped[int] = mapped_column(
        BigInteger().with_variant(Integer, "sqlite"), primary_key=True
    )
    """The unique identifier of the process. Auto-incremented."""

    scenario_id: Mapped[int] = mapped_column(ForeignKey("Scenario.id"))
    """The unique identifier of the scenario. Foreign key to :attr:`Scenario.id`."""
    scenario: Mapped["Scenario"] = relationship("Scenario", back_populates="processes")
    """The scenario."""

    name: Mapped[str] = mapped_column(Text)
    """A name for the process. If set, it must be unique within the scenario."""

    name_short: Mapped[str] = mapped_column(Text, nullable=True)
    """An optional short name for the process."""

    dispatchable: Mapped[bool] = mapped_column(Boolean)
    """Whether the bus is ready for departure."""

    duration: Mapped[timedelta] = mapped_column(Interval, nullable=True)
    """The duration of this process in seconds."""

    electric_power: Mapped[float] = mapped_column(Float, nullable=True)
    """The peak electric power required by this process in kW. Actual power consumption might be lower. It implies the 
    charging equipment to be provided."""

    availability: Mapped[List[Tuple[datetime, datetime]]] = mapped_column(
        postgresql.JSONB().with_variant(JSON(), "sqlite"), nullable=True  # type: ignore
    )
    """Temporal availability of this process represented by a list of start and end times. Null means this process is 
    always available."""

    plans: Mapped[List["Plan"]] = relationship(
        "Plan",
        secondary="AssocPlanProcess",
        back_populates="processes",
        viewonly=True,
    )

    areas: Mapped[List["Area"]] = relationship(
        "Area",
        secondary="AssocAreaProcess",
        back_populates="processes",
    )

    assoc_area_processes: Mapped[List["AssocAreaProcess"]] = relationship(
        "AssocAreaProcess", viewonly=True
    )

    __table_args__ = tuple(_table_args_list)

    def __repr__(self) -> str:
        return f"<Process(id={self.id}, name={self.name}, duration={self.duration}, electric_power={self.electric_power})>"


@event.listens_for(Process, "before_insert")
@event.listens_for(Process, "before_update")
def validate_duration_and_power(_: Any, __: Any, target: Process) -> None:
    """
    Validates the duration and electric power of a Process before inserting or updating it in the database.
    :param _: Unused parameter, typically the mapper or class being listened to.
    :param __: Unused parameter, typically the instance being inserted or updated.
    :param target:  The Process instance being validated.
    :return: None. Raises ValueError if validation fails.
    """
    if target.duration is not None and target.duration < timedelta(0):
        raise ValueError("Duration must be non-negative")
    if target.electric_power is not None and target.electric_power < 0:
        raise ValueError("Electric power must be non-negative")


class AssocPlanProcess(Base):
    """The association table for the many-to-many relationship between :class:`Plan` and :class:`Process`."""

    __tablename__ = "AssocPlanProcess"

    id: Mapped[int] = mapped_column(
        BigInteger().with_variant(Integer, "sqlite"), primary_key=True
    )
    """The unique identifier of the association. Auto-incremented. Needed for django."""

    scenario_id: Mapped[int] = mapped_column(ForeignKey("Scenario.id"))
    """The unique identifier of the scenario. Foreign key to :attr:`Scenario.id`."""
    scenario: Mapped["Scenario"] = relationship(
        "Scenario", back_populates="assoc_plan_processes"
    )
    """The scenario."""

    plan_id: Mapped[int] = mapped_column(ForeignKey("Plan.id"))
    """The unique identifier of the plan. Foreign key to :attr:`Plan.id`."""
    plan: Mapped["Plan"] = relationship("Plan")
    """The plan."""

    process_id: Mapped[int] = mapped_column(ForeignKey("Process.id"))
    """The unique identifier of the process. Foreign key to :attr:`Process.id`."""
    process: Mapped["Process"] = relationship("Process")
    """The process."""

    ordinal: Mapped[int] = mapped_column(Integer)
    """The ordinal of the process in the plan."""

    def __repr__(self) -> str:
        return f"<AssocPlanProcess(id={self.id}, Plan={self.plan}, Process={self.process}, ordinal={self.ordinal})>"


class AssocAreaProcess(Base):
    """The association table for the many-to-many relationship between :class:`Area` and :class:`Process`."""

    __tablename__ = "AssocAreaProcess"

    id: Mapped[int] = mapped_column(
        BigInteger().with_variant(Integer, "sqlite"), primary_key=True
    )
    """The unique identifier of the association. Auto-incremented. Needed for django."""

    area_id: Mapped[int] = mapped_column(ForeignKey("Area.id"))
    """The unique identifier of the area. Foreign key to :attr:`Area.id`."""
    area: Mapped["Area"] = relationship("Area", overlaps="areas,processes")
    """The area."""

    process_id: Mapped[int] = mapped_column(ForeignKey("Process.id"))
    """The unique identifier of the process. Foreign key to :attr:`Process.id`."""
    process: Mapped["Process"] = relationship("Process", overlaps="areas,processes")
    """The process."""

    def __repr__(self) -> str:
        return f"<AssocAreaProcess(id={self.id}, area_id={self.area_id}, process_id={self.process_id})>"
