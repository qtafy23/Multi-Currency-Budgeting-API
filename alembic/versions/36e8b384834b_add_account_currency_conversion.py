"""add_account_currency_conversion

Revision ID: 36e8b384834b
Revises: d03b7e291c54
Create Date: 2026-10-20 22:01:25.163881

"""
from typing import Sequence, Union

from alembic import op
import sqlalchemy as sa


# revision identifiers, used by Alembic.
revision: str = '36e8b384834b'
down_revision: Union[str, None] = 'd03b7e291c54'
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    op.execute(
        "ALTER TYPE transactiontype "
        "ADD VALUE IF NOT EXISTS 'CONVERSION'"
    )

    op.add_column(
        "transactions",
        sa.Column(
            "exchange_rate",
            sa.Numeric(18, 8),
            nullable=True,
        ),
    )


def downgrade() -> None:
    op.drop_column("transactions", "exchange_rate")
