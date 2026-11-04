"""Scope transaction idempotency keys to their owner.

Revision ID: 8a7c2e91b640
Revises: d221672db222
"""

import sqlalchemy as sa

from alembic import op

revision = "8a7c2e91b640"
down_revision = "d221672db222"
branch_labels = None
depends_on = None


def upgrade() -> None:
    op.add_column("transactions", sa.Column("user_id", sa.Integer()))
    op.execute(
        sa.text(
            "UPDATE transactions SET user_id = accounts.user_id "
            "FROM accounts WHERE transactions.account_id = accounts.id"
        )
    )
    op.alter_column("transactions", "user_id", nullable=False)
    op.create_foreign_key(
        "fk_transactions_user_id_users",
        "transactions",
        "users",
        ["user_id"],
        ["id"],
    )
    op.drop_index("ix_transactions_idempotency_key", table_name="transactions")
    op.create_unique_constraint(
        "uq_transactions_user_id_idempotency_key",
        "transactions",
        ["user_id", "idempotency_key"],
    )


def downgrade() -> None:
    # Reverting requires globally unique keys again. PostgreSQL rejects this
    # atomically if users have reused a key; no transactions are discarded.
    op.create_index(
        "ix_transactions_idempotency_key",
        "transactions",
        ["idempotency_key"],
        unique=True,
    )
    op.drop_constraint(
        "uq_transactions_user_id_idempotency_key",
        "transactions",
        type_="unique",
    )
    op.drop_constraint(
        "fk_transactions_user_id_users",
        "transactions",
        type_="foreignkey",
    )
    op.drop_column("transactions", "user_id")
