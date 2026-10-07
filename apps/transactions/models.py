from datetime import datetime, timezone

from sqlalchemy import (
    Column,
    DateTime,
    Enum,
    ForeignKey,
    Integer,
    Numeric,
    String,
)

from core.constants.currency import Currency
from core.constants.transaction import TransactionType
from core.db import Base


class Transaction(Base):
    __tablename__ = "transactions"

    id = Column(Integer, primary_key=True)
    account_id = Column(Integer, ForeignKey("accounts.id"), nullable=False)
    external_id = Column(String, nullable=True, unique=True, index=True)
    idempotency_key = Column(String, nullable=True, unique=True, index=True)
    type = Column(Enum(TransactionType), nullable=False)
    original_amount = Column(Numeric(12, 2), nullable=True)
    converted_amount = Column(Numeric(12, 2), nullable=True)
    original_currency = Column(Enum(Currency), nullable=True)
    account_currency = Column(Enum(Currency), nullable=True)
    amount = Column(Numeric(12, 2), nullable=False)
    balance_after = Column(Numeric(12, 2), nullable=False)
    currency = Column(String, nullable=False)
    category = Column(String, nullable=True, index=True)
    note = Column(String, nullable=True)
    created_at = Column(DateTime, default=lambda: datetime.now(timezone.utc))

    def __repr__(self) -> str:
        return (
            f"<Transaction(id={self.id}, account_id={self.account_id}, "
            f"type={self.type}, amount={self.amount})>"
        )
