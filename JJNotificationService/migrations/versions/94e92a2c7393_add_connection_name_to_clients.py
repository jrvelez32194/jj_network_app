"""Add connection_name to clients"""

from alembic import op
import sqlalchemy as sa

# Revision identifiers, used by Alembic
revision = '20251002_add_connection_name'
down_revision = '775404f4e449'
branch_labels = None
depends_on = None


def upgrade():
    op.add_column('clients', sa.Column('connection_name', sa.String(), nullable=True))


def downgrade():
    op.drop_column('clients', 'connection_name')
