"""fix client status uppercase

Revision ID: 99b518eaf6e6
Revises: cdd6bf91e90c
Create Date: 2025-10-03 06:41:06.066374

"""
from typing import Sequence, Union

from alembic import op
import sqlalchemy as sa


# revision identifiers, used by Alembic.
revision: str = '99b518eaf6e6'
down_revision: Union[str, Sequence[str], None] = 'cdd6bf91e90c'
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade():
  op.alter_column("clients", "status",
                  server_default="PAID",
                  existing_type=sa.String(),
                  nullable=False
                  )
  op.execute(
    "UPDATE clients SET status = UPPER(status) WHERE status IN ('paid','due','limited','cutoff');"
  )


def downgrade():
  op.alter_column("clients", "status",
                  server_default="paid",
                  existing_type=sa.String(),
                  nullable=False
                  )
