"""v2.3.0

Revision ID: baef3598b52c
Revises: 7483339ae654
Create Date: 2024-02-27 12:54:29.303194

"""
from typing import Sequence, Union

from alembic import op
import sqlalchemy as sa


# revision identifiers, used by Alembic.
revision: str = "baef3598b52c"
down_revision: Union[str, None] = "7483339ae654"
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    # ### commands auto generated by Alembic - please adjust! ###
    op.add_column("Scenario", sa.Column("manager_id", sa.Integer(), nullable=True))
    # ### end Alembic commands ###


def downgrade() -> None:
    # ### commands auto generated by Alembic - please adjust! ###
    op.drop_column("Scenario", "manager_id")
    # ### end Alembic commands ###