"""Add refresh-token version for logout revocation.

Revision ID: b2f684ab91d0
Revises: 06e3eee5a4f1
Create Date: 2026-10-07

"""
from typing import Sequence, Union

import sqlalchemy as sa

from alembic import op

# revision identifiers, used by Alembic.
revision: str = "b2f684ab91d0"
down_revision: Union[str, None] = "06e3eee5a4f1"
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, None] = None


def upgrade() -> None:
    op.add_column(
        "users",
        sa.Column(
            "refresh_token_version",
            sa.Integer(),
            server_default="0",
            nullable=False,
        ),
    )


def downgrade() -> None:
    op.drop_column("users", "refresh_token_version")
