"""expand alembic_version.version_num column length
   + add created_at and alter sent_at in message_logs

Revision ID: 20251002_expand_version_num
Revises: 20251002_add_connection_name
Create Date: 2025-10-02 16:00:00
"""
from typing import Sequence, Union
from alembic import op
import sqlalchemy as sa

# revision identifiers, used by Alembic.
revision: str = "20251002_expand_version_num"
down_revision: Union[str, Sequence[str], None] = "20251002_add_connection_name"
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    # expand version_num to varchar(128)
    op.alter_column(
        "alembic_version",
        "version_num",
        type_=sa.String(128),
        existing_type=sa.String(32),
        existing_nullable=False,
    )

    # safely add created_at if not exists
    op.execute("""
        ALTER TABLE message_logs
        ADD COLUMN IF NOT EXISTS created_at TIMESTAMP WITH TIME ZONE DEFAULT now() NOT NULL
    """)

    # alter sent_at to TIMESTAMP WITH TIME ZONE
    op.alter_column(
        "message_logs",
        "sent_at",
        existing_type=sa.DateTime(),
        type_=sa.DateTime(timezone=True),
        existing_nullable=True,
    )


def downgrade() -> None:
    # revert sent_at back to TIMESTAMP WITHOUT TIME ZONE
    op.alter_column(
        "message_logs",
        "sent_at",
        existing_type=sa.DateTime(timezone=True),
        type_=sa.DateTime(),
        existing_nullable=True,
    )

    # drop created_at
    op.drop_column("message_logs", "created_at")

    # shrink back to varchar(32) (⚠️ will fail if data > 32 chars exists)
    op.alter_column(
        "alembic_version",
        "version_num",
        type_=sa.String(32),
        existing_type=sa.String(128),
        existing_nullable=False,
    )
