"""v10.0.0 - Add SpatiaLite support

Revision ID: 3a62f62ef264
Revises: 6e96cbfb3523
Create Date: 2025-08-13 16:53:13.847480

This migration handles the PostgreSQL-specific changes from adding SpatiaLite support.
Most changes use SQLAlchemy's .with_variant() which doesn't affect PostgreSQL schema,
but some constraints were restructured.
"""
from typing import Sequence, Union

from alembic import op
import sqlalchemy as sa


# revision identifiers, used by Alembic.
revision: str = "3a62f62ef264"
down_revision: Union[str, None] = "6e96cbfb3523"
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    # Drop the CheckConstraint from Process table (moved to event listener)
    op.drop_constraint("positive_duration_and_power_check", "Process", type_="check")

    # The Event table's ExcludeConstraint should already exist (no change needed)
    # It's now added via DDL event but was already there in PostgreSQL

    # The Temperatures table's array length check should already exist (no change needed)
    # It's now added via DDL event but was already there in PostgreSQL

    # Note: The UUID column type change in Scenario table from UUID(as_uuid=True) to Uuid
    # doesn't require a migration as both map to the same PostgreSQL UUID type.
    # The server_default change from func.gen_random_uuid() to Python's uuid.uuid4
    # only affects new records and doesn't require schema migration.


def downgrade() -> None:
    # Re-add the CheckConstraint to Process table
    op.create_check_constraint(
        "positive_duration_and_power_check",
        "Process",
        sa.text(
            "(duration IS NULL) OR "
            "(duration IS NOT NULL AND duration >= '00:00:00') OR "
            "(electric_power IS NULL) OR "
            "(electric_power IS NOT NULL AND electric_power >= 0)"
        ),
    )

    # Note: The Event and Temperatures constraints don't need changes as they
    # remain functionally the same in PostgreSQL
