"""replace due_date with billing_day

Revision ID: 079bdd0eacb1
Revises: 99b518eaf6e6
Create Date: 2025-10-03 22:18:35.180837

"""
from typing import Sequence, Union

from alembic import op
import sqlalchemy as sa


# revision identifiers, used by Alembic.
revision: str = '079bdd0eacb1'
down_revision: Union[str, Sequence[str], None] = '99b518eaf6e6'
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade():
  # 1. Drop old column
  with op.batch_alter_table("clients") as batch_op:
    batch_op.drop_column("due_date")

  # 2. Add new column
  with op.batch_alter_table("clients") as batch_op:
    batch_op.add_column(
      sa.Column("billing_day", sa.Integer(), nullable=False, server_default="0")
    )

  # Remove default constraint after migration (optional, keeps schema clean)
  op.execute("ALTER TABLE clients ALTER COLUMN billing_day DROP DEFAULT;")


def downgrade():
  # Reverse: drop billing_day and add back due_date
  with op.batch_alter_table("clients") as batch_op:
    batch_op.drop_column("billing_day")

  with op.batch_alter_table("clients") as batch_op:
    batch_op.add_column(
      sa.Column("due_date", sa.DateTime(), nullable=True)
    )