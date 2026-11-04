"""Store the original budget warning on transactions.

Revision ID: e3a7c9d2f614
Revises: 8a7c2e91b640
"""

import sqlalchemy as sa
from alembic import op

revision = "e3a7c9d2f614"
down_revision = "8a7c2e91b640"
branch_labels = None
depends_on = None


def upgrade() -> None:
    op.add_column("transactions", sa.Column("budget_warning", sa.String(), nullable=True))


def downgrade() -> None:
    op.drop_column("transactions", "budget_warning")
