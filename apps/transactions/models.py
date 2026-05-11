from enum import Enum as PyEnum
from datetime import datetime, timezone
from decimal import Decimal

from sqlalchemy import Column, Integer, Numeric, String, DateTime, ForeignKey, Enum
from core.db import Base


class TransactionType(str, PyEnum):
    INCOME = "income"
    EXPENSE = "expense"


class Transaction(Base):
    __tablename__ = "transactions"

    id = Column(Integer, primary_key=True)
    account_id = Column(Integer, ForeignKey("accounts.id"), nullable=False)
    type = Column(Enum(TransactionType), nullable=False)
    amount = Column(Numeric(12, 2), nullable=False)
    balance_after = Column(Numeric(12, 2), nullable=False)
    currency = Column(String, nullable=False)
    note = Column(String, nullable=True)
    created_at = Column(DateTime, default=lambda: datetime.now(timezone.utc))

    def __repr__(self) -> str:
        return f"<Transaction(id={self.id}, account_id={self.account_id}, type={self.type}, amount={self.amount})>"
