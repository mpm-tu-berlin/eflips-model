"""5.1.3

Revision ID: 86302241f50a
Revises: e232e88e379d
Create Date: 2024-08-06 13:06:39.069716

"""
from typing import Sequence, Union

from alembic import op
import sqlalchemy as sa


# revision identifiers, used by Alembic.
revision: str = "86302241f50a"
down_revision: Union[str, None] = "e232e88e379d"
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    # ### commands auto generated by Alembic - please adjust! ###
    sql = r"""
    alter table public."Event"
    drop constraint filled_fields_type_combination;

    alter table public."Event"
    add constraint filled_fields_type_combination
        check (((station_id IS NOT NULL) AND ((event_type)::text = 'CHARGING_OPPORTUNITY'::text OR
                                              (event_type)::text = 'STANDBY_DEPARTURE'::text)) OR
               ((area_id IS NOT NULL) AND (subloc_no IS NOT NULL) AND ((event_type)::text = ANY
                                                                       (ARRAY [('CHARGING_DEPOT'::character varying)::text, ('SERVICE'::character varying)::text, ('STANDBY_DEPARTURE'::character varying)::text, ('STANDBY'::character varying)::text, ('PRECONDITIONING'::character varying)::text]))) OR
               ((trip_id IS NOT NULL) AND (subloc_no IS NULL) AND ((event_type)::text = 'DRIVING'::text)));
    
    """
    op.execute(sql)
    # ### end Alembic commands ###


def downgrade() -> None:
    # ### commands auto generated by Alembic - please adjust! ###
    sql = r"""
    alter table public."Event"
    drop constraint filled_fields_type_combination;

    alter table public."Event"
    add constraint filled_fields_type_combination
        check (((station_id IS NOT NULL) AND (subloc_no IS NOT NULL) AND((event_type)::text = 'CHARGING_OPPORTUNITY'::text) OR
               ((area_id IS NOT NULL) AND (subloc_no IS NOT NULL) AND ((event_type)::text = ANY
                                                                       (ARRAY [('CHARGING_DEPOT'::character varying)::text, ('SERVICE'::character varying)::text, ('STANDBY_DEPARTURE'::character varying)::text, ('STANDBY'::character varying)::text, ('PRECONDITIONING'::character varying)::text]))) OR
               ((trip_id IS NOT NULL) AND (subloc_no IS NULL) AND ((event_type)::text = 'DRIVING'::text)));
    """
    op.execute(sql)
    # ### end Alembic commands ###
