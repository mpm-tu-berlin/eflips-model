import logging
import os

from eflips.model import Base, create_engine, setup_database


class TestSetupDatabase:
    def test_setup_database_leaves_logging_alone(self):
        """
        setup_database() runs alembic's stamp command internally. Alembic's env.py must not
        apply alembic.ini's logging config to the calling process, or it silences every logger
        the host application already configured.
        """
        logger = logging.getLogger("host.application")
        root_level = logging.root.level
        root_handlers = list(logging.root.handlers)

        url = os.environ["DATABASE_URL"]
        engine = create_engine(url, echo=False)
        Base.metadata.drop_all(engine)
        try:
            setup_database(engine)

            assert not logger.disabled
            assert logging.root.level == root_level
            assert logging.root.handlers == root_handlers
        finally:
            Base.metadata.drop_all(engine)
