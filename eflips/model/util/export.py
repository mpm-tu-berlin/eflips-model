#! /usr/bin/env python3

"""
Utility script to export a scenario to a file.
"""
import gzip
import os
import pickle
from argparse import ArgumentParser
from typing import List, Dict

import psycopg2
from sqlalchemy import create_engine
from sqlalchemy.orm import (
    class_mapper,
    make_transient,
    Session,
    RelationshipDirection,
)

from eflips.model import Base
from eflips.model.depot import Area as Area
from eflips.model.depot import AssocAreaProcess as AssocAreaProcess
from eflips.model.depot import AssocPlanProcess as AssocPlanProcess
from eflips.model.depot import Depot as Depot
from eflips.model.depot import Plan as Plan
from eflips.model.depot import Process as Process
from eflips.model.general import (
    AssocVehicleTypeVehicleClass as AssocVehicleTypeVehicleClass,
)
from eflips.model.general import ConsumptionLut as ConsumptionLut
from eflips.model.general import Temperatures as Temperatures
from eflips.model.general import BatteryType as BatteryType
from eflips.model.general import Event as Event
from eflips.model.general import Scenario as Scenario
from eflips.model.general import Vehicle as Vehicle
from eflips.model.general import VehicleClass as VehicleClass
from eflips.model.general import VehicleType as VehicleType
from eflips.model.network import AssocRouteStation as AssocRouteStation
from eflips.model.network import Line as Line
from eflips.model.network import Route as Route
from eflips.model.network import Station as Station
from eflips.model.schedule import Rotation as Rotation
from eflips.model.schedule import StopTime as StopTime
from eflips.model.schedule import Trip as Trip

ALL_CLASSES_WITH_SCENARIO_ID = [
    BatteryType,
    Vehicle,
    VehicleClass,
    VehicleType,
    Event,
    Line,
    Route,
    Station,
    AssocRouteStation,
    StopTime,
    Trip,
    Rotation,
    Depot,
    Plan,
    Area,
    Process,
    AssocPlanProcess,
    ConsumptionLut,
    Temperatures,
]
ALL_PURE_ASSOC_CLASSES = [AssocAreaProcess, AssocVehicleTypeVehicleClass]
ALL_TABLE_CLASSES = ALL_CLASSES_WITH_SCENARIO_ID + ALL_PURE_ASSOC_CLASSES + [Scenario]


def start_counting_foreign_keys_at(
    start: Dict[str, int], objs: List[Base]
) -> List[Base]:
    """
    Take a collection of related objects, and set the foreign key IDs on the local and remote side of each relationship
    to values >= the given start value. This is useful when importing a scenario, as it allows to set the IDs of the
    objects to be imported to values that are not already present in the database.
    :param start: A dictionary containing the starting value for each class.
    :param objs: A list of Base objects.
    :return: The same list of Base objects, but with the foreign key IDs set to values >= the given start value.
    """

    # In a first pass, find how much we need to offset the IDs by
    # If e.g. our IDs range from 1 to 6, and the base is 10, we need to add 9 to each ID
    offsets = {}
    for obj in objs:
        assert len(class_mapper(obj.__class__).primary_key) == 1
        primary_key_name = class_mapper(obj.__class__).primary_key[0].name
        primary_key = obj.__dict__[primary_key_name]
        if primary_key is None:
            raise ValueError(f"Primary key of {obj} is None.")
        if obj.__class__.__name__ not in offsets:
            offsets[obj.__class__.__name__] = (
                start[obj.__class__.__name__] - primary_key
            )
        else:
            offsets[obj.__class__.__name__] = max(
                offsets[obj.__class__.__name__],
                start[obj.__class__.__name__] - primary_key,
            )

    # In a second pass, set the IDs to the new values. Do that both if they are on the local or remote side of a
    # relationship.
    for obj in objs:
        assert len(class_mapper(obj.__class__).primary_key) == 1
        primary_key_name = class_mapper(obj.__class__).primary_key[0].name
        primary_key = obj.__dict__[primary_key_name]
        obj.__dict__[primary_key_name] = primary_key + offsets[obj.__class__.__name__]

        for relationship in class_mapper(obj.__class__).relationships:
            if relationship.direction in (
                RelationshipDirection.ONETOMANY,
                RelationshipDirection.MANYTOMANY,
            ):
                # We are on the remote side of a one-to-many relationship. No need to change anything.
                continue
            assert len(relationship.local_columns) == 1
            relationship_column_name = next(iter(relationship.local_columns)).name
            relationship_column = obj.__dict__[relationship_column_name]
            if relationship_column is not None:
                relationship_column = (
                    relationship_column + offsets[str(relationship.argument)]
                )
                obj.__dict__[relationship_column_name] = relationship_column

    return objs


def get_or_update_max_sequence_number(
    conn: psycopg2.extensions.connection, do_update: bool = False
) -> Dict[str, int]:
    """
    Loads the maximum sequence number for each table in the database. Can be used to determine the starting point for
    the sequence numbers when importing a scenario. Or to fix the sequence numbers after importing a scenario.
    :param conn: An open database connection.
    :param do_update: If True, the sequence counters will also be updated in the database to continue counting after
    the maximum sequence number.
    :return: A dictionary containing the maximum sequence number for each table.
    """
    SEQUENCE_NUMBER_SUFFIX = "_id_seq"
    KEY_NAME = "id"  # The name of the primary key column in the tables
    result = {}
    with conn.cursor() as cur:
        for table in ALL_TABLE_CLASSES:
            table_name = table.__name__
            query = f'SELECT MAX("{KEY_NAME}") FROM "{table_name}"'
            cur.execute(query)
            res = cur.fetchone()
            max_id = res[0] + 1 if res is not None and res[0] is not None else 0
            result[table_name] = max_id
            if do_update:
                cur.execute(
                    f'ALTER SEQUENCE "{table_name + SEQUENCE_NUMBER_SUFFIX}" RESTART WITH {max_id + 1}'
                )
                cur.execute(
                    f'SELECT NEXTVAL(\'"public"."{table_name + SEQUENCE_NUMBER_SUFFIX}"\')'
                )
                res = cur.fetchone()
                new_max_id = res[0] if res is not None else None
                if new_max_id is None or new_max_id <= max_id:
                    raise ValueError(
                        f"Sequence {table_name + SEQUENCE_NUMBER_SUFFIX} did not restart properly. "
                        f"It is still at {new_max_id}"
                    )
    return result


def disconnect_obj(obj: Base) -> Base:
    """
    Take an object and disconnect it from the database session. This will make it a pure Python object.

    This is done by
    - setting the primary key to None
    - setting the object to transient state
    - setting all ids for the foreign keys to None

    :param obj: An SQLAlchemy object.
    :return: The same object, but disconnected from the database session.
    """
    make_transient(obj)
    return obj


def extract_scenario(scenario_id: int, session: Session) -> List[Base]:
    """
    Extracts the scenario with the given ID from the database. It will be turned into a set of Base objects, which are
    no longer attached to the database.
    :param scenario_id: The ID of the scenario to extract.
    :param session: An active database session.
    :return: A list of Base objects representing the scenario.
    """
    all_related_objects = []

    scenario = session.query(Scenario).filter(Scenario.id == scenario_id).one_or_none()
    if not scenario:
        raise ValueError(f"No scenario with ID {scenario_id} found.")

    # Load all objects related to the scenario
    for cls in ALL_CLASSES_WITH_SCENARIO_ID:
        assert hasattr(cls, "scenario_id")
        query = session.query(cls).filter(cls.scenario_id == scenario_id)
        for obj in query:
            all_related_objects.append(disconnect_obj(obj))

    # Load all the association tables
    for cls in ALL_PURE_ASSOC_CLASSES:
        if cls == AssocAreaProcess:
            query = session.query(AssocAreaProcess).join(Area).filter(Area.scenario_id == scenario_id)  # type: ignore
        elif cls == AssocVehicleTypeVehicleClass:
            query = session.query(AssocVehicleTypeVehicleClass).join(VehicleType).filter(VehicleType.scenario_id == scenario_id)  # type: ignore
        else:
            raise ValueError(f"Unknown association class {cls}.")
        for obj in query:
            all_related_objects.append(disconnect_obj(obj))

    scenario.parent_id = None  # type: ignore
    scenario.parent = None  # type: ignore
    all_related_objects.append(disconnect_obj(scenario))
    return all_related_objects


if __name__ == "__main__":
    args = ArgumentParser()
    group = args.add_mutually_exclusive_group(required=True)
    group.add_argument(
        "-l",
        "--list",
        action="store_true",
        help="List available scenarios.",
    )
    group.add_argument(
        "--output_file",
        "-o",
        type=str,
        help="The file to which the scenario should be exported.",
    )
    args.add_argument(
        "-s",
        "--scenario_ids",
        "--scenario-ids",
        "--scenario_id",
        "--scenario-id",
        metavar="scenario_ids",
        nargs="+",
        type=int,
        required=False,
        help="The numerical IDs of the scenarios to export. Run without arguments to see a list of available scenarios."
        "If no ID is provided, all scenarios will be exported/listed.",
    )
    args.add_argument(
        "-d",
        "--database_url",
        "--database-url",
        type=str,
        required=False,
        help="The URL of the database to which to connect to. Should be of the form "
        "'postgresql://user:password@host:port/database'. If none is provided, DATABASE_URL environment variable "
        "will be used.",
    )
    parsed = args.parse_args()
    del args

    # Get the database URL
    database_url = parsed.database_url or os.environ.get("DATABASE_URL")
    if not database_url:
        raise ValueError(
            "No database URL provided. Please provide one using the --database_url argument or the "
            "DATABASE_URL environment variable."
        )

    engine = create_engine(database_url)
    with Session(engine) as session:
        try:
            # Get the scenario ID. If it is not provied, load all scenarios.
            if parsed.scenario_ids:
                scenario_ids = parsed.scenario_ids
            else:
                scenario_id_result = session.query(Scenario.id)
                scenario_ids = [result[0] for result in scenario_id_result]

            if parsed.list:
                for scenario_id in scenario_ids:
                    scenario = (
                        session.query(Scenario).filter(Scenario.id == scenario_id).one()
                    )
                    print(f"Scenario {scenario.id}: {scenario.name}")
                exit(0)

            all_objects = []
            for scenario_id in scenario_ids:
                all_objects.extend(extract_scenario(scenario_id, session))

            # Get the alembic version
            with session.connection().connection.driver_connection.cursor() as cur:  # type: ignore
                cur.execute("SELECT * FROM alembic_version")
                alembic_version_str = cur.fetchone()[0]

            # Create a dictionary with the alembic version and the objects
            to_dump = {"alembic_version": alembic_version_str, "objects": all_objects}

            # Write the objects to a compressed file.
            with gzip.open(parsed.output_file, "wb") as file:
                pickle.dump(to_dump, file)

        finally:
            session.rollback()
            session.close()
