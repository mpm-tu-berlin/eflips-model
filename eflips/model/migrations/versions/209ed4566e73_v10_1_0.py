"""add energy_source to VehicleType

Revision ID: 209ed4566e73
Revises: 921afffb2adf
Create Date: 2026-03-06 09:33:26.303428

"""
from typing import Sequence, Union

from alembic import op
import sqlalchemy as sa


# revision identifiers, used by Alembic.
revision: str = "209ed4566e73"
down_revision: Union[str, None] = "921afffb2adf"
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    op.add_column("VehicleType", sa.Column("energy_source", sa.String(), nullable=True))
    op.execute("UPDATE \"VehicleType\" SET energy_source = 'BATTERY_ELECTRIC'")
    op.alter_column("VehicleType", "energy_source", nullable=False)


def downgrade() -> None:
    op.drop_column("VehicleType", "energy_source")
