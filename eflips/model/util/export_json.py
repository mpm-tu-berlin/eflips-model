#!/usr/bin/env python3

"""
Utility script to export a scenario to a JSON file.

This script exports eflips-model database data to a JSON format compatible with
django-simba imports. It handles serialization of SQLAlchemy objects including
geometry types, enums, datetimes, and relationships.
"""

import json
import os
from argparse import ArgumentParser
from datetime import datetime, timedelta
from enum import Enum
from typing import Any, Callable
from uuid import UUID

from geoalchemy2 import WKBElement
from geoalchemy2.shape import to_shape
from sqlalchemy import inspect
from sqlalchemy.orm import Mapper
from sqlalchemy.orm import Query, Session, RelationshipDirection

from eflips.model import Base, create_engine, Scenario, Trip, TripType
from eflips.model.depot import Area, AssocAreaProcess
from eflips.model.general import AssocVehicleTypeVehicleClass, VehicleType
from eflips.model.util.export import (
    ALL_CLASSES_WITH_SCENARIO_ID,
    ALL_PURE_ASSOC_CLASSES,
)

# ---------------------------------------------------------------------------
# django-simba compatibility constants
# ---------------------------------------------------------------------------

# Mapping from eflips-model class names to django-simba expected names
MODEL_NAME_MAPPING: dict[str, str] = {
    "ConsumptionLut": "Consumption",
}

# Default values for fields that django-simba requires but eflips-model may have as null
FIELD_DEFAULTS: dict[str, dict[str, Any]] = {
    "VehicleType": {
        "length": 0.0,
        "width": 0.0,
        "height": 0.0,
    },
    "Scenario": {
        "manager": 1,  # Default to admin user
    },
}

# Extra fields to add that django-simba expects but don't exist in eflips-model
EXTRA_FIELDS: dict[str, dict[str, Any]] = {
    "Scenario": {
        "tco_result": None,
    },
    "VehicleType": {
        "max_consumption": None,
        "vehicle_classes": [],  # M2M field, empty if no classes defined
    },
}

# Computed fields derived from serialized values
# Format: {class_name: {field_name: callable(serialized_result) -> value}}
COMPUTED_FIELDS: dict[str, dict[str, Callable[[dict[str, Any]], Any]]] = {
    "Scenario": {
        "scenario_type": lambda r: "SOURCE_FILE",
    },
    "VehicleType": {
        "max_consumption": lambda r: 2 * r["consumption"]
        if r.get("consumption") is not None
        else None,
    },
}


def get_foreign_key_columns(mapper: Mapper[Any]) -> set[str]:
    """
    Get column names that are foreign keys (with _id suffix).

    Args:
        mapper: SQLAlchemy mapper for the class

    Returns:
        Set of column names that are foreign keys
    """
    fk_columns = set()
    for relationship in mapper.relationships:
        if relationship.direction == RelationshipDirection.MANYTOONE:
            for column in relationship.local_columns:
                fk_columns.add(column.name)
    return fk_columns


def convert_geometry_to_3d(wkt: str) -> str:
    """
    Convert a 2D WKT geometry string to 3D with Z=0.

    Examples:
        POINT(13.19 52.69) -> POINT Z (13.19 52.69 0)
        LINESTRING(13.19 52.69, 13.20 52.70) -> LINESTRING Z (13.19 52.69 0, 13.20 52.70 0)
        POLYGON((13.19 52.69, ...)) -> POLYGON Z ((13.19 52.69 0, ...))
    """
    if " Z " in wkt or " Z(" in wkt:
        # Already 3D
        return wkt

    # Handle POINT
    if wkt.startswith("POINT"):
        # POINT(x y) -> POINT Z (x y 0)
        inner = wkt[wkt.index("(") + 1 : wkt.rindex(")")]
        coords = inner.strip().split()
        if len(coords) == 2:
            return f"POINT Z ({coords[0]} {coords[1]} 0)"
        return wkt

    # Handle LINESTRING
    if wkt.startswith("LINESTRING"):
        inner = wkt[wkt.index("(") + 1 : wkt.rindex(")")]
        coords_list = inner.split(",")
        new_coords = []
        for coord in coords_list:
            parts = coord.strip().split()
            if len(parts) == 2:
                new_coords.append(f"{parts[0]} {parts[1]} 0")
            else:
                new_coords.append(coord.strip())
        return f"LINESTRING Z ({', '.join(new_coords)})"

    # Handle POLYGON
    if wkt.startswith("POLYGON"):
        # POLYGON((x1 y1, x2 y2, ...)) -> POLYGON Z ((x1 y1 0, x2 y2 0, ...))
        # Find the inner part (may have multiple rings)
        inner_start = wkt.index("(") + 1
        inner_end = wkt.rindex(")")
        inner = wkt[inner_start:inner_end]

        # Process each ring (separated by ), ()
        rings = []
        depth = 0
        current_ring = ""
        for char in inner:
            if char == "(":
                depth += 1
                if depth == 1:
                    continue
            elif char == ")":
                depth -= 1
                if depth == 0:
                    # End of a ring
                    coords_list = current_ring.split(",")
                    new_coords = []
                    for coord in coords_list:
                        parts = coord.strip().split()
                        if len(parts) == 2:
                            new_coords.append(f"{parts[0]} {parts[1]} 0")
                        else:
                            new_coords.append(coord.strip())
                    rings.append(f"({', '.join(new_coords)})")
                    current_ring = ""
                    continue
            if depth >= 1:
                current_ring += char

        return f"POLYGON Z ({', '.join(rings)})"

    return wkt


def serialize_value(value: Any) -> Any:
    """
    Serialize a single value based on its type.

    Args:
        value: The value to serialize

    Returns:
        A JSON-serializable representation of the value
    """
    if value is None:
        return None

    # Handle Geometry (WKBElement)
    if isinstance(value, WKBElement):
        shape = to_shape(value)
        # Get EWKT with SRID
        srid = value.srid if value.srid else 4326
        wkt = shape.wkt
        # Convert to 3D
        wkt_3d = convert_geometry_to_3d(wkt)
        return f"SRID={srid};{wkt_3d}"

    # Handle datetime with timezone
    if isinstance(value, datetime):
        if value.tzinfo is not None:
            return value.isoformat()
        else:
            # Assume UTC if no timezone
            return value.isoformat() + "+00:00"

    # Handle Enum
    if isinstance(value, Enum):
        return value.name

    # Handle timedelta/Interval
    if isinstance(value, timedelta):
        total_seconds = int(value.total_seconds())
        hours = total_seconds // 3600
        minutes = (total_seconds % 3600) // 60
        seconds = total_seconds % 60
        return f"{hours:02d}:{minutes:02d}:{seconds:02d}"

    # Handle UUID
    if isinstance(value, UUID):
        return str(value)

    # Handle dict (JSON/JSONB) - pass through
    if isinstance(value, dict):
        return value

    # Handle list (Array types) - recursively serialize
    if isinstance(value, list):
        return [serialize_value(item) for item in value]

    # Handle basic types
    if isinstance(value, (int, float, str, bool)):
        return value

    # Fallback to string representation
    return str(value)


def get_many_to_many_relationships(obj: Base) -> dict[str, list[int]]:
    """
    Get many-to-many relationship data as lists of IDs.

    Args:
        obj: An SQLAlchemy object

    Returns:
        A dict mapping relationship names to lists of related object IDs
    """
    result = {}
    mapper = inspect(obj.__class__)

    for rel in mapper.relationships:
        if rel.direction == RelationshipDirection.MANYTOMANY:
            # Get the related objects
            related_objects = getattr(obj, rel.key, None)
            if related_objects is not None:
                # Extract IDs from related objects
                ids = []
                for related_obj in related_objects:
                    if hasattr(related_obj, "id"):
                        ids.append(related_obj.id)
                if ids:
                    result[rel.key] = ids

    return result


def serialize_object(obj: Base) -> dict[str, Any]:
    """
    Serialize an SQLAlchemy object to a dict.

    Foreign key columns have their _id suffix stripped to match
    django-simba's expected format (e.g., scenario_id -> scenario).
    Some non-FK columns like manager_id are also treated as references.

    Args:
        obj: An SQLAlchemy object

    Returns:
        A JSON-serializable dict representation of the object
    """
    result = {}
    mapper = inspect(obj.__class__)
    class_name = obj.__class__.__name__

    # Get FK columns to know which ones need _id suffix stripped
    fk_columns = get_foreign_key_columns(mapper)

    # Additional columns to treat as FK-like (strip _id suffix)
    # These are columns that reference external IDs but aren't defined as FK relationships
    fk_like_columns = {"manager_id"}

    # Get field defaults for this class
    field_defaults = FIELD_DEFAULTS.get(class_name, {})

    # Serialize all columns
    for column in mapper.columns:
        column_name = column.key
        value = getattr(obj, column_name, None)

        # Strip _id suffix from FK columns and FK-like columns for django-simba compatibility
        output_name = column_name
        if column_name.endswith("_id") and (
            column_name in fk_columns or column_name in fk_like_columns
        ):
            output_name = column_name[:-3]  # Remove "_id" suffix

        serialized_value = serialize_value(value)

        # Apply default value if the field is None and has a configured default
        if serialized_value is None and output_name in field_defaults:
            serialized_value = field_defaults[output_name]

        result[output_name] = serialized_value

    # Add many-to-many relationships as lists of IDs
    m2m_rels = get_many_to_many_relationships(obj)
    result.update(m2m_rels)

    # Add extra fields that django-simba expects but don't exist in eflips-model
    extra_fields = EXTRA_FIELDS.get(class_name, {})
    for field_name, default_value in extra_fields.items():
        if field_name not in result:
            result[field_name] = default_value

    # Apply computed fields (may overwrite extra-field defaults)
    computed_fields = COMPUTED_FIELDS.get(class_name, {})
    for field_name, compute_fn in computed_fields.items():
        result[field_name] = compute_fn(result)

    return result


def export_scenario_to_json(
    scenario_id: int, session: Session
) -> dict[str, list[dict[str, Any]]]:
    """
    Export a scenario and all related objects to a JSON-compatible dict.

    Args:
        scenario_id: The ID of the scenario to export
        session: An active database session

    Returns:
        A dict with class names as keys and lists of serialized objects as values
    """
    result: dict[str, list[dict[str, Any]]] = {}

    # Load the scenario
    scenario = session.query(Scenario).filter(Scenario.id == scenario_id).one_or_none()
    if not scenario:
        raise ValueError(f"No scenario with ID {scenario_id} found.")

    # Set sensible loaded_mass defaults for trips before export
    session.query(Trip).filter(
        Trip.scenario_id == scenario_id,
        Trip.trip_type == TripType.EMPTY,
    ).update({"loaded_mass": 0})
    session.query(Trip).filter(
        Trip.scenario_id == scenario_id,
        Trip.trip_type == TripType.PASSENGER,
        Trip.loaded_mass == None,
    ).update({"loaded_mass": 1360})

    # Add the scenario first
    result["Scenario"] = [serialize_object(scenario)]

    # Load all objects with scenario_id
    for cls in ALL_CLASSES_WITH_SCENARIO_ID:
        class_name = cls.__name__
        # Map class name for django-simba compatibility
        output_class_name = MODEL_NAME_MAPPING.get(class_name, class_name)
        assert hasattr(cls, "scenario_id")
        query: Query[Any] = session.query(cls).filter(cls.scenario_id == scenario_id)
        objects = query.all()
        if objects:
            result[output_class_name] = [serialize_object(obj) for obj in objects]

    # Load the pure association tables
    for cls in ALL_PURE_ASSOC_CLASSES:
        class_name = cls.__name__
        # Map class name for django-simba compatibility
        output_class_name = MODEL_NAME_MAPPING.get(class_name, class_name)
        if cls == AssocAreaProcess:
            query = (
                session.query(AssocAreaProcess)
                .join(Area)
                .filter(Area.scenario_id == scenario_id)
            )
        elif cls == AssocVehicleTypeVehicleClass:
            query = (
                session.query(AssocVehicleTypeVehicleClass)
                .join(VehicleType)
                .filter(VehicleType.scenario_id == scenario_id)
            )
        else:
            continue

        objects = query.all()
        if objects:
            result[output_class_name] = [serialize_object(obj) for obj in objects]

    return result


def list_scenarios(session: Session, scenario_ids: list[int] | None = None) -> None:
    """
    List available scenarios.

    Args:
        session: An active database session
        scenario_ids: Optional list of specific scenario IDs to list
    """
    if scenario_ids:
        scenarios = session.query(Scenario).filter(Scenario.id.in_(scenario_ids)).all()
    else:
        scenarios = session.query(Scenario).all()

    for scenario in scenarios:
        print(f"Scenario {scenario.id}: {scenario.name}")


def main() -> None:
    """CLI entry point."""
    parser = ArgumentParser(
        description="Export eflips-model scenario data to JSON format."
    )

    group = parser.add_mutually_exclusive_group(required=True)
    group.add_argument(
        "-l",
        "--list",
        action="store_true",
        help="List available scenarios.",
    )
    group.add_argument(
        "-o",
        "--output",
        type=str,
        help="Output JSON file path.",
    )

    parser.add_argument(
        "-s",
        "--scenario-id",
        "--scenario_id",
        dest="scenario_ids",
        nargs="+",
        type=int,
        help="The numerical ID(s) of the scenario(s) to export.",
    )

    parser.add_argument(
        "-d",
        "--database-url",
        "--database_url",
        dest="database_url",
        type=str,
        help=(
            "The URL of the database to connect to. Should be of the form "
            "'postgresql://user:password@host:port/database'. "
            "If not provided, the DATABASE_URL environment variable will be used."
        ),
    )

    args = parser.parse_args()

    # Get the database URL
    database_url = args.database_url or os.environ.get("DATABASE_URL")
    if not database_url:
        raise ValueError(
            "No database URL provided. Please provide one using the --database-url "
            "argument or the DATABASE_URL environment variable."
        )

    engine = create_engine(database_url)

    with Session(engine) as session:
        try:
            if args.list:
                list_scenarios(session, args.scenario_ids)
                return

            # Determine which scenario(s) to export
            if args.scenario_ids:
                scenario_ids = args.scenario_ids
            else:
                # Export all scenarios if none specified
                scenario_ids = [s.id for s in session.query(Scenario.id).all()]

            # Export each scenario and merge results
            all_data: dict[str, list[dict[str, Any]]] = {}
            for scenario_id in scenario_ids:
                scenario_data = export_scenario_to_json(scenario_id, session)
                for class_name, objects in scenario_data.items():
                    if class_name not in all_data:
                        all_data[class_name] = []
                    all_data[class_name].extend(objects)

            # Write to output file
            with open(args.output, "w", encoding="utf-8") as f:
                json.dump(all_data, f, indent=2, ensure_ascii=False)

            print(f"Exported {len(scenario_ids)} scenario(s) to {args.output}")

        finally:
            session.rollback()
            session.close()


if __name__ == "__main__":
    main()
