"""remove unique constraint from messenger_id

Revision ID: e33c2eb173c9
Revises: 2843e13b8acd
Create Date: 2025-12-20 10:17:30.386602

"""
from typing import Sequence, Union

from alembic import op
import sqlalchemy as sa


# revision identifiers, used by Alembic.
revision: str = 'e33c2eb173c9'
down_revision: Union[str, Sequence[str], None] = '2843e13b8acd'
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade():
  op.drop_constraint(
    constraint_name="clients_messenger_id_key",  # name may vary
    table_name="clients",
    type_="unique"
  )


def downgrade():
  op.create_unique_constraint(
    "clients_messenger_id_key",
    "clients",
    ["messenger_id"]
  )
