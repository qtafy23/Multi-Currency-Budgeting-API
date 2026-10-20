"""Add currency to budgets.

Revision ID: d03b7e291c54
Revises: c41d8a0b7f26
Create Date: 2026-10-07

"""
from typing import Sequence, Union

import sqlalchemy as sa

from alembic import op

# revision identifiers, used by Alembic.
revision: str = "d03b7e291c54"
down_revision: Union[str, None] = "c41d8a0b7f26"
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, None] = None


def upgrade() -> None:
    op.add_column(
        "budgets",
        sa.Column(
            "currency",
            sa.String(length=3),
            server_default="EUR",
            nullable=False,
        ),
    )


def downgrade() -> None:
    op.drop_column("budgets", "currency")
