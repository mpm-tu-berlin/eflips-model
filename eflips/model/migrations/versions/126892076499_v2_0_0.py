"""v2.0.0

Revision ID: 126892076499
Revises: 9e29124f8ce6
Create Date: 2024-02-05 17:12:38.671705

"""
from typing import Sequence, Union

from alembic import op
import sqlalchemy as sa


# revision identifiers, used by Alembic.
revision: str = "126892076499"
down_revision: Union[str, None] = "9e29124f8ce6"
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    op.alter_column(
        "Trip",
        "level_of_loading",
        existing_type=sa.Float(),
        nullable=True,
        new_column_name="loaded_mass",
    )
    op.add_column("VehicleType", sa.Column("allowed_mass", sa.Float(), nullable=True))


def downgrade() -> None:
    op.drop_column("VehicleType", "allowed_mass")
    op.alter_column(
        "Trip",
        "loaded_mass",
        existing_type=sa.Float(),
        nullable=True,
        new_column_name="level_of_loading",
    )
