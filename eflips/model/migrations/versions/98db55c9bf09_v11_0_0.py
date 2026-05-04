"""v11.0.0 — Re-introduce Z (3D) on network geometries.

Revision ID: 98db55c9bf09
Revises: 209ed4566e73
Create Date: 2026-04-29

Restores the POINTZ / LINESTRINGZ columns that were dropped at v10.0.0
(``6e96cbfb3523``). Existing 2D rows are lifted to Z=0 via ``ST_Force3DZ``;
populate realistic elevations via the ``eflips-ingest`` elevation backfill.

Body is a literal mirror of the ``downgrade()`` from
``6e96cbfb3523_v10_0_0.py`` (and ``downgrade()`` here is the literal mirror of
its ``upgrade()``), since that direction was already exercised at v10 release.

PostGIS-only at the migration level: ``op.add_column`` with a Geometry type
emits PostgreSQL-style ``ALTER TABLE … ADD COLUMN geometry(POINTZ,4326)`` DDL,
which SpatiaLite does not parse. SpatiaLite users should rebuild from scratch
via ``setup_database()`` (which uses GeoAlchemy2's ``AddGeometryColumn``); the
schema produced at v11 head is identical regardless of the path taken.
"""
from typing import Sequence, Union

from alembic import op
import sqlalchemy as sa
from geoalchemy2 import Geometry
from sqlalchemy import text


# revision identifiers, used by Alembic.
revision: str = "98db55c9bf09"
down_revision: Union[str, None] = "209ed4566e73"
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    # Station.geom: POINT -> POINTZ
    op.add_column(
        "Station",
        sa.Column(
            "geom_temp",
            Geometry(
                geometry_type="POINTZ",
                srid=4326,
                dimension=3,
                from_text="ST_GeomFromEWKT",
                name="geometry",
                _spatial_index_reflected=True,
            ),
            nullable=True,
        ),
    )
    op.execute(
        text(
            """
            UPDATE "Station"
            SET geom_temp = ST_Force3DZ(geom, 0)
            WHERE geom IS NOT NULL
            """
        )
    )
    op.drop_column("Station", "geom")
    op.alter_column("Station", "geom_temp", new_column_name="geom")

    # Route.geom: LINESTRING -> LINESTRINGZ
    op.add_column(
        "Route",
        sa.Column(
            "geom_temp",
            Geometry(
                geometry_type="LINESTRINGZ",
                srid=4326,
                dimension=3,
                from_text="ST_GeomFromEWKT",
                name="geometry",
                _spatial_index_reflected=True,
            ),
            nullable=True,
        ),
    )
    op.execute(
        text(
            """
            UPDATE "Route"
            SET geom_temp = ST_Force3DZ(geom, 0)
            WHERE geom IS NOT NULL
            """
        )
    )
    op.drop_column("Route", "geom")
    op.alter_column("Route", "geom_temp", new_column_name="geom")

    # AssocRouteStation.location: POINT -> POINTZ
    op.add_column(
        "AssocRouteStation",
        sa.Column(
            "location_temp",
            Geometry(
                geometry_type="POINTZ",
                srid=4326,
                dimension=3,
                from_text="ST_GeomFromEWKT",
                name="geometry",
                _spatial_index_reflected=True,
            ),
            nullable=True,
        ),
    )
    op.execute(
        text(
            """
            UPDATE "AssocRouteStation"
            SET location_temp = ST_Force3DZ(location, 0)
            WHERE location IS NOT NULL
            """
        )
    )
    op.drop_column("AssocRouteStation", "location")
    op.alter_column("AssocRouteStation", "location_temp", new_column_name="location")


def downgrade() -> None:
    # AssocRouteStation.location: POINTZ -> POINT
    op.add_column(
        "AssocRouteStation",
        sa.Column(
            "location_temp",
            Geometry(
                geometry_type="POINT",
                srid=4326,
                from_text="ST_GeomFromEWKT",
                name="geometry",
            ),
            nullable=True,
        ),
    )
    op.execute(
        text(
            """
            UPDATE "AssocRouteStation"
            SET location_temp = ST_Force2D(location)
            WHERE location IS NOT NULL
            """
        )
    )
    op.drop_column("AssocRouteStation", "location")
    op.alter_column("AssocRouteStation", "location_temp", new_column_name="location")

    # Route.geom: LINESTRINGZ -> LINESTRING
    op.add_column(
        "Route",
        sa.Column(
            "geom_temp",
            Geometry(
                geometry_type="LINESTRING",
                srid=4326,
                from_text="ST_GeomFromEWKT",
                name="geometry",
            ),
            nullable=True,
        ),
    )
    op.execute(
        text(
            """
            UPDATE "Route"
            SET geom_temp = ST_Force2D(geom)
            WHERE geom IS NOT NULL
            """
        )
    )
    op.drop_column("Route", "geom")
    op.alter_column("Route", "geom_temp", new_column_name="geom")

    # Station.geom: POINTZ -> POINT
    op.add_column(
        "Station",
        sa.Column(
            "geom_temp",
            Geometry(
                geometry_type="POINT",
                srid=4326,
                from_text="ST_GeomFromEWKT",
                name="geometry",
            ),
            nullable=True,
        ),
    )
    op.execute(
        text(
            """
            UPDATE "Station"
            SET geom_temp = ST_Force2D(geom)
            WHERE geom IS NOT NULL
            """
        )
    )
    op.drop_column("Station", "geom")
    op.alter_column("Station", "geom_temp", new_column_name="geom")
