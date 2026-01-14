"""Decouple message_logs from client and template

Revision ID: f7d03f49da99
Revises: 968d0a3df9d1
Create Date: 2026-01-14 07:39:02.574179

"""
from typing import Sequence, Union

from alembic import op
import sqlalchemy as sa


# revision identifiers, used by Alembic.
revision: str = 'f7d03f49da99'
down_revision: Union[str, Sequence[str], None] = '968d0a3df9d1'
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade():
  # 1️⃣ DELETE ALL EXISTING MESSAGE LOGS
  op.execute("DELETE FROM message_logs")

  # 2️⃣ Add new columns
  op.add_column(
    "message_logs",
    sa.Column("title", sa.String(), nullable=False)
  )
  op.add_column(
    "message_logs",
    sa.Column("message", sa.Text(), nullable=False)
  )

  # 3️⃣ Drop foreign key constraints
  op.drop_constraint(
    "message_logs_client_id_fkey",
    "message_logs",
    type_="foreignkey"
  )
  op.drop_constraint(
    "message_logs_template_id_fkey",
    "message_logs",
    type_="foreignkey"
  )

  # 4️⃣ Drop old columns
  op.drop_column("message_logs", "client_id")
  op.drop_column("message_logs", "template_id")

def downgrade():
  # 1️⃣ Re-add old columns
  op.add_column(
    "message_logs",
    sa.Column("client_id", sa.Integer(), nullable=True)
  )
  op.add_column(
    "message_logs",
    sa.Column("template_id", sa.Integer(), nullable=True)
  )

  # 2️⃣ Restore foreign keys
  op.create_foreign_key(
    "message_logs_client_id_fkey",
    "message_logs",
    "clients",
    ["client_id"],
    ["id"]
  )
  op.create_foreign_key(
    "message_logs_template_id_fkey",
    "message_logs",
    "templates",
    ["template_id"],
    ["id"]
  )

  # 3️⃣ Drop new columns
  op.drop_column("message_logs", "message")
  op.drop_column("message_logs", "connection_name")

