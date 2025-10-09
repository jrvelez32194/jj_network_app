"""Update Billing Date to nullable

Revision ID: cf9011c0c826
Revises: 21f9441578f3
Create Date: 2025-10-08 08:28:42.342155

"""
from typing import Sequence, Union

from alembic import op
import sqlalchemy as sa
from sqlalchemy.dialects import postgresql

# revision identifiers, used by Alembic.
revision: str = 'cf9011c0c826'
down_revision: Union[str, Sequence[str], None] = '21f9441578f3'
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade():
  op.alter_column("clients", "billing_date",
                  existing_type=sa.Date(),
                  nullable=True)


def downgrade():
  op.alter_column("clients", "billing_date",
                  existing_type=sa.Date(),
                  nullable=False)