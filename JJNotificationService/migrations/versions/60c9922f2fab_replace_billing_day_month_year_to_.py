"""replace_billing_day_month_year_to_billing_date

Revision ID: 60c9922f2fab
Revises: 4a01793c7143
Create Date: 2025-10-08 05:59:18.958233

"""
from typing import Sequence, Union

from alembic import op
import sqlalchemy as sa

# revision identifiers, used by Alembic.
revision: str = '60c9922f2fab'
down_revision: Union[str, Sequence[str], None] = '4a01793c7143'
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade():
    # 1. Add billing_date (nullable allowed)
    op.add_column("clients", sa.Column("billing_date", sa.Date(), nullable=True))

    conn = op.get_bind()

    # 2. Explicitly set billing_date = NULL for all existing rows
    conn.execute(sa.text("""
        UPDATE clients
        SET billing_date = NULL
    """))

    # 3. Drop old columns
    op.drop_column("clients", "billing_day")
    op.drop_column("clients", "billing_month")
    op.drop_column("clients", "billing_year")


def downgrade():
    # Recreate old columns
    op.add_column("clients", sa.Column("billing_year", sa.Integer(), nullable=True))
    op.add_column("clients", sa.Column("billing_month", sa.Integer(), nullable=True))
    op.add_column("clients", sa.Column("billing_day", sa.Integer(), nullable=True))

    conn = op.get_bind()

    # Backfill old values from billing_date if available
    conn.execute(sa.text("""
        UPDATE clients
        SET billing_year = EXTRACT(YEAR FROM billing_date)::int,
            billing_month = EXTRACT(MONTH FROM billing_date)::int,
            billing_day = EXTRACT(DAY FROM billing_date)::int
        WHERE billing_date IS NOT NULL
    """))

    # Drop new column
    op.drop_column("clients", "billing_date")
