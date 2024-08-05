#! /usr/bin/env python3

"""
Utility script to import a scenario from a file.
"""
import gzip
import os
import pickle
from argparse import ArgumentParser
from typing import Dict, List, Union

from sqlalchemy import create_engine
from sqlalchemy.orm import Session

import eflips.model
from eflips.model import Base
from eflips.model.util.export import (
    ALL_TABLE_CLASSES,
    start_counting_foreign_keys_at,
    get_or_update_max_sequence_number,
)

if __name__ == "__main__":
    args = ArgumentParser()
    args.add_argument(
        "--input_file",
        "-i",
        type=str,
        required=True,
        help="The file to which the scenario should be exported.",
    )
    args.add_argument(
        "--create_schema",
        "--create-schema",
        "-c",
        action="store_true",
        help="Whether to create the schema in the database. If not set, it is assumed that the schema already exists.",
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

    database_url = parsed.database_url or os.environ.get("DATABASE_URL")
    if not database_url:
        raise ValueError(
            "No database URL provided. Please provide one using the --database_url argument or the "
            "DATABASE_URL environment variable."
        )

    with gzip.open(parsed.input_file, "rb") as file:
        loaded: Dict[str, Union[List[Base], str]] = pickle.load(file)

    all_objects = loaded["objects"]
    assert isinstance(all_objects, list)
    for obj in all_objects:
        assert isinstance(obj, Base)
    alembic_version_from_file = loaded["alembic_version"]
    assert isinstance(alembic_version_from_file, str)

    engine = create_engine(database_url)

    if parsed.create_schema:
        eflips.model.setup_database(engine)

    with Session(engine) as session:
        try:
            # Validate the alembic version
            with session.connection().connection.driver_connection.cursor() as cur:  # type: ignore
                cur.execute("SELECT * FROM alembic_version")
                alembic_version_from_db = cur.fetchone()[0]
                if alembic_version_from_db != alembic_version_from_file:
                    raise ValueError(
                        f"Database alembic version ({alembic_version_from_db}) does not match the file's version "
                        f"({alembic_version_from_file})."
                    )

            # Find the maximum IDs in the database and update the sequence numbers
            starts = get_or_update_max_sequence_number(session.connection().connection.driver_connection, do_update=False)  # type: ignore
            all_objects = start_counting_foreign_keys_at(starts, all_objects)

            # Put the objects into the database
            with session.no_autoflush:
                for obj in all_objects:
                    session.add(obj)
            session.flush()

            # Update the sequence numbers in the database
            get_or_update_max_sequence_number(
                session.connection().connection.driver_connection,  # type: ignore
                do_update=True,
            )
        except Exception as e:
            print(e)
            session.rollback()
            raise
        finally:
            session.commit()
            session.close()
