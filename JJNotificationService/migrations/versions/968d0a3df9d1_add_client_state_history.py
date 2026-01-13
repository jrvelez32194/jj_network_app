"""Add Client State History

Revision ID: 968d0a3df9d1
Revises: e33c2eb173c9
Create Date: 2026-01-13 18:32:55.221744

"""
from typing import Sequence, Union

from alembic import op
import sqlalchemy as sa


# revision identifiers, used by Alembic.
revision: str = '968d0a3df9d1'
down_revision: Union[str, Sequence[str], None] = 'e33c2eb173c9'
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None



def upgrade():
    op.create_table(
        "client_state_history",
        sa.Column("id", sa.Integer(), primary_key=True),
        sa.Column(
            "client_id",
            sa.Integer(),
            sa.ForeignKey("clients.id", ondelete="CASCADE"),
            nullable=False,
        ),
        sa.Column("prev_state", sa.String(length=20), nullable=False),
        sa.Column("new_state", sa.String(length=20), nullable=False),
        sa.Column("reason", sa.String(length=50), nullable=True),
        sa.Column(
            "created_at",
            sa.DateTime(),
            server_default=sa.func.now(),
            nullable=False,
        ),
    )

    op.create_index(
        "ix_client_state_history_client_id",
        "client_state_history",
        ["client_id"],
    )

    op.create_index(
        "ix_client_state_history_created_at",
        "client_state_history",
        ["created_at"],
    )


def downgrade():
    op.drop_index("ix_client_state_history_created_at", table_name="client_state_history")
    op.drop_index("ix_client_state_history_client_id", table_name="client_state_history")
    op.drop_table("client_state_history")
