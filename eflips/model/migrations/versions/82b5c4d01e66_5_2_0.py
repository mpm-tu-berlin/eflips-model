"""5.2.0

Revision ID: 82b5c4d01e66
Revises: 986abf14da65
Create Date: 2024-09-04 18:24:53.339476

"""
from typing import Sequence, Union

from alembic import op
import sqlalchemy as sa
from sqlalchemy.dialects import postgresql

# revision identifiers, used by Alembic.
revision: str = "82b5c4d01e66"
down_revision: Union[str, None] = "986abf14da65"
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    # ### commands auto generated by Alembic - please adjust! ###
    op.create_table(
        "Temperatures",
        sa.Column("id", sa.BigInteger(), nullable=False),
        sa.Column("scenario_id", sa.BigInteger(), nullable=False),
        sa.Column("name", sa.Text(), nullable=False),
        sa.Column("use_only_time", sa.Boolean(), nullable=False),
        sa.Column(
            "datetimes", postgresql.ARRAY(sa.DateTime(timezone=True)), nullable=False
        ),
        sa.Column("data", postgresql.ARRAY(sa.Float()), nullable=False),
        sa.ForeignKeyConstraint(
            ["scenario_id"],
            ["Scenario.id"],
        ),
        sa.PrimaryKeyConstraint("id"),
        sa.UniqueConstraint("scenario_id", "id"),
    )
    # ### end Alembic commands ###


def downgrade() -> None:
    # ### commands auto generated by Alembic - please adjust! ###
    op.drop_table("Temperatures")
    # ### end Alembic commands ###