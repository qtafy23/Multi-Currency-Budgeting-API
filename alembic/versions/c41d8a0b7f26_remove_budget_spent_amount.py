"""Remove stored budget spending; derive it from transactions.

Revision ID: c41d8a0b7f26
Revises: b2f684ab91d0
Create Date: 2026-10-07

"""
from typing import Sequence, Union

import sqlalchemy as sa

from alembic import op

# revision identifiers, used by Alembic.
revision: str = "c41d8a0b7f26"
down_revision: Union[str, None] = "b2f684ab91d0"
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, None] = None


def upgrade() -> None:
    op.drop_column("budgets", "spent_amount")


def downgrade() -> None:
    op.add_column(
        "budgets",
        sa.Column(
            "spent_amount",
            sa.Numeric(12, 2),
            server_default="0",
            nullable=False,
        ),
    )
