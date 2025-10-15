"""Add SPIKING to ConnectionState enum

Revision ID: 2843e13b8acd
Revises: cf9011c0c826
Create Date: 2025-10-15 23:32:11.458666

"""
from typing import Sequence, Union

from alembic import op
import sqlalchemy as sa


# revision identifiers, used by Alembic.
revision: str = '2843e13b8acd'
down_revision: Union[str, Sequence[str], None] = 'cf9011c0c826'
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade():
  conn = op.get_bind()
  # ✅ Check if the enum type exists first
  result = conn.execute(
    "SELECT 1 FROM pg_type WHERE typname = 'connectionstate';"
  ).fetchone()

  if result:
    op.execute("ALTER TYPE connectionstate ADD VALUE IF NOT EXISTS 'SPIKING';")
  else:
    print(
      "⚠️ Skipping SPIKING enum addition: 'connectionstate' type not found.")


def downgrade():
  # PostgreSQL doesn’t support removing enum values directly
  pass