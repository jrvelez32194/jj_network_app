"""Add billing_month and billing_year

Revision ID: 4a01793c7143
Revises: 27f8f8b9f959
Create Date: 2025-10-06 15:52:40.168821

"""
from typing import Sequence, Union

from alembic import op
import sqlalchemy as sa
from datetime import datetime
from sqlalchemy.dialects import postgresql

# revision identifiers, used by Alembic.
revision: str = '4a01793c7143'
down_revision: Union[str, Sequence[str], None] = '27f8f8b9f959'
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade():
  # Add new columns with default values
  op.add_column("clients",
                sa.Column("billing_month", sa.Integer(), nullable=False,
                          server_default=str(datetime.now().month)))
  op.add_column("clients",
                sa.Column("billing_year", sa.Integer(), nullable=False,
                          server_default=str(datetime.now().year)))

  # Remove the server_default after populating existing rows
  op.alter_column("clients", "billing_month", server_default=None)
  op.alter_column("clients", "billing_year", server_default=None)


def downgrade():
  op.drop_column("clients", "billing_month")
  op.drop_column("clients", "billing_year")