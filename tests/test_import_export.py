import pickle

from eflips.model import Base
from eflips.model.util.export import (
    extract_scenario,
    start_counting_foreign_keys_at,
    get_or_update_max_sequence_number,
)
from test_general import TestGeneral


class TestExport(TestGeneral):
    def test_export_reimport(self, session, scenario, tmp_path):
        scenario_ids = [scenario.id]

        all_objects = []
        for scenario_id in scenario_ids:
            all_objects.extend(extract_scenario(scenario_id, session))

        # Get the alembic version
        cur = session.connection().connection.driver_connection.cursor()
        try:
            cur.execute("SELECT * FROM alembic_version")
            alembic_version_str = cur.fetchone()[0]
        finally:
            cur.close()

        # Create a dictionary with the alembic version and the objects
        to_dump = {"alembic_version": alembic_version_str, "objects": all_objects}

        serialized = pickle.dumps(to_dump)

        loaded = pickle.loads(serialized)

        assert isinstance(all_objects, list)
        for obj in all_objects:
            assert isinstance(obj, Base)
        alembic_version_from_file = loaded["alembic_version"]
        assert isinstance(alembic_version_from_file, str)

        # Validate the alembic version
        cur = session.connection().connection.driver_connection.cursor()
        try:
            cur.execute("SELECT * FROM alembic_version")
            alembic_version_from_db = cur.fetchone()[0]
            if alembic_version_from_db != alembic_version_from_file:
                raise ValueError(
                    f"Database alembic version ({alembic_version_from_db}) does not match the file's version "
                    f"({alembic_version_from_file})."
                )
        finally:
            cur.close()

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

        session.commit()

        # Verify that now there are two scenarios in the database
        assert session.query(scenario.__class__).count() == 2
