"""add client state/status/speed_limit

Revision ID: cdd6bf91e90c
Revises: 20251002_expand_version_num
Create Date: 2025-10-03 06:27:38.531164

"""
from typing import Sequence, Union
from alembic import op
import sqlalchemy as sa

# revision identifiers, used by Alembic.
revision: str = 'cdd6bf91e90c'
down_revision: Union[str, Sequence[str], None] = '20251002_expand_version_num'
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    """Upgrade schema."""
    # Add new columns to clients table
    op.add_column('clients', sa.Column('state', sa.String(), nullable=False, server_default="UNKNOWN"))
    op.add_column('clients', sa.Column('due_date', sa.DateTime(), nullable=True))
    op.add_column('clients', sa.Column('status', sa.String(), nullable=False, server_default="paid"))
    op.add_column('clients', sa.Column('speed_limit', sa.String(), nullable=False, server_default="unlimited"))


def downgrade() -> None:
    """Downgrade schema."""
    # Remove added columns
    op.drop_column('clients', 'speed_limit')
    op.drop_column('clients', 'status')
    op.drop_column('clients', 'due_date')
    op.drop_column('clients', 'state')
