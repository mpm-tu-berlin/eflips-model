#! /usr/bin/env python3

"""
Utility script to export a scenario to a file.
"""
import gzip
import os
import pickle
from argparse import ArgumentParser
from copy import deepcopy
from typing import List

from sqlalchemy import create_engine
from sqlalchemy.orm import (
    class_mapper,
    joinedload,
    make_transient,
    make_transient_to_detached,
    Session,
)

from eflips.model import Area, AssocAreaProcess, Base, Scenario
from eflips.model.general import AssocVehicleTypeVehicleClass, VehicleType


def extract_scenarioo(scenario_id: int, session: Session) -> List[Base]:
    """
    Extracts the scenario with the given ID from the database. It will be turned into a set of Base objects, which are
    no longer attached to the database.
    :param scenario_id: The ID of the scenario to extract.
    :param session: An active database session.
    :return: A list of Base objects representing the scenario.
    """
    scenario = session.query(Scenario).filter(Scenario.id == scenario_id).one_or_none()
    if not scenario:
        raise ValueError(f"No scenario with ID {scenario_id} found.")

    # Go through the scenario and extract all the objects.
    result = [scenario]

    list_of_objs = [
        scenario.vehicle_types,
        scenario.battery_types,
        scenario.vehicles,
        scenario.vehicle_classes,
        scenario.lines,
        scenario.routes,
        scenario.stations,
        scenario.assoc_route_stations,
        scenario.stop_times,
        scenario.trips,
        scenario.rotations,
        scenario.events,
        scenario.depots,
        scenario.plans,
        scenario.areas,
        scenario.processes,
        scenario.assoc_plan_processes,
    ]

    for obj_list in list_of_objs:
        for obj in obj_list:
            make_transient(obj)
            obj.id = None
            result.append(obj)

    # For two pure association_tables, we need to extract the objects in a different way.
    assocs_vehicle_type_vehicle_class = (
        session.query(AssocVehicleTypeVehicleClass)
        .join(VehicleType)
        .filter(VehicleType.scenario_id == scenario_id)
        .all()
    )
    for assoc in assocs_vehicle_type_vehicle_class:
        make_transient(assoc)
        assoc.id = None
        result.append(assoc)

    assocs_area_process = (
        session.query(AssocAreaProcess)
        .join(Area)
        .filter(Area.scenario_id == scenario_id)
        .all()
    )
    for assoc in assocs_area_process:
        make_transient(assoc)
        assoc.id = None
        result.append(assoc)

    # Cut off the scenario from the database.
    make_transient(scenario)
    scenario.id = None

    return result


def extract_scenario(scenario_id: int, session: Session) -> List[Base]:
    # Load the original scenario and related objects
    scenario = session.query(Scenario).filter(Scenario.id == scenario_id).one()
    list_of_objs = [
        scenario.vehicle_types,
        scenario.battery_types,
        scenario.vehicles,
        scenario.vehicle_classes,
        scenario.lines,
        scenario.routes,
        scenario.stations,
        scenario.assoc_route_stations,
        scenario.stop_times,
        scenario.trips,
        scenario.rotations,
        scenario.events,
        scenario.depots,
        scenario.plans,
        scenario.areas,
        scenario.processes,
        scenario.assoc_plan_processes,
    ]

    # Create a deep copy of the scenario graph
    # deepcopy will attempt to recursively copy all attributes, which can include SQLAlchemy internal state
    # Depending on your SQLAlchemy setup, you might need to adjust how relationships and foreign keys are copied
    new_scenario = deepcopy(scenario)
    new_scenario.id = None  # Assuming the primary key is auto-generated

    # Inspect and copy relationships
    for relationship in class_mapper(Scenario).relationships:
        related_objects = getattr(scenario, relationship.key)
        if isinstance(related_objects, list):
            # Handle one-to-many relationships
            new_related_objects = []
            for obj in related_objects:
                new_obj = deepcopy(obj)
                new_obj.id = None  # Reset primary key for related object
                new_related_objects.append(new_obj)
            setattr(new_scenario, relationship.key, new_related_objects)
        else:
            # Handle one-to-one relationships
            new_obj = deepcopy(related_objects)
            if new_obj:
                new_obj.id = None
                setattr(new_scenario, relationship.key, new_obj)


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
    args = args.parse_args()

    # Get the database URL
    database_url = args.database_url or os.environ.get("DATABASE_URL")
    if not database_url:
        raise ValueError(
            "No database URL provided. Please provide one using the --database_url argument or the "
            "DATABASE_URL environment variable."
        )

    engine = create_engine(database_url)
    with Session(engine) as session:
        try:
            # Get the scenario ID. If it is not provied, load all scenarios.
            if args.scenario_ids:
                scenario_ids = args.scenario_ids
            else:
                scenario_id_result = session.query(Scenario.id)
                scenario_ids = [result[0] for result in scenario_id_result]

            if args.list:
                for scenario_id in scenario_ids:
                    scenario = (
                        session.query(Scenario).filter(Scenario.id == scenario_id).one()
                    )
                    print(f"Scenario {scenario.id}: {scenario.name}")
                exit(0)

            all_objects = []
            for scenario_id in scenario_ids:
                all_objects.extend(extract_scenario(scenario_id, session))

            # Write the objects to a compressed file.
            with gzip.open(args.output_file, "wb") as file:
                pickle.dump(all_objects, file)

        finally:
            session.close()

    # TESTING: Clear the database
    # Base.metadata.drop_all(engine)
    # Base.metadata.create_all(engine)

    # TESTING: Load the scenario back into the database
    with gzip.open(args.output_file, "rb") as file:
        all_objects = pickle.load(file)
    with Session(engine) as session:
        try:
            for obj in all_objects:
                make_transient(obj)
                session.add(obj)
        except Exception as e:
            print(e)
            session.rollback()
            raise
        finally:
            session.commit()
            session.close()
