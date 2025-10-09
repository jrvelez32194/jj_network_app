"""Add amt_monthly to clients

Revision ID: 21f9441578f3
Revises: 60c9922f2fab
Create Date: 2025-10-08 07:53:25.161956

"""
from typing import Sequence, Union

from alembic import op
import sqlalchemy as sa
from sqlalchemy.dialects import postgresql

# revision identifiers, used by Alembic.
revision: str = '21f9441578f3'
down_revision: Union[str, Sequence[str], None] = '60c9922f2fab'
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
  op.add_column('clients', sa.Column('amt_monthly', sa.Float(), nullable=True,
                                     server_default="0"))


def downgrade() -> None:
  op.drop_column('clients', 'amt_monthly')
