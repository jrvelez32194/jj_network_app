"""replace DUE with UNPAID

Revision ID: 27f8f8b9f959
Revises: 079bdd0eacb1
Create Date: 2025-10-03 23:43:48.760795

"""
from typing import Sequence, Union

from alembic import op
import sqlalchemy as sa


# revision identifiers, used by Alembic.
revision: str = '27f8f8b9f959'
down_revision: Union[str, Sequence[str], None] = '079bdd0eacb1'
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade():
  # Update all clients with status = "DUE" to "UNPAID"
  op.execute(
    "UPDATE clients SET status = 'UNPAID' WHERE status = 'DUE';"
  )


def downgrade():
  # Rollback: convert UNPAID back to DUE
  op.execute(
    "UPDATE clients SET status = 'DUE' WHERE status = 'UNPAID';"
  )