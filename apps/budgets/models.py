from datetime import datetime, timezone

from sqlalchemy import Column, DateTime
from sqlalchemy import Enum as SAEnum
from sqlalchemy import ForeignKey, Integer, Numeric, String, UniqueConstraint

from core.constants.budgets import BudgetPeriod
from core.constants.currency import Currency
from core.db import Base


class Budget(Base):
    __tablename__ = "budgets"
    __table_args__ = (
        UniqueConstraint(
            "user_id", "category", "period", name="uq_user_category_period"
        ),
    )

    id = Column(Integer, primary_key=True)
    user_id = Column(
        Integer, ForeignKey("users.id"), nullable=False, index=True
    )
    category = Column(String, nullable=False, index=True)
    limit = Column(Numeric(12, 2), nullable=False)
    currency = Column(
        String(3),
        nullable=False,
        default=Currency.EUR.value,
        server_default=Currency.EUR.value,
    )
    period = Column(
        SAEnum(BudgetPeriod), nullable=False, default=BudgetPeriod.MONTHLY
    )
    created_at = Column(DateTime, default=lambda: datetime.now(timezone.utc))
    updated_at = Column(
        DateTime,
        default=lambda: datetime.now(timezone.utc),
        onupdate=lambda: datetime.now(timezone.utc),
    )

    def __repr__(self) -> str:
        return (
            f"<Budget(id={self.id}, user_id={
                      self.user_id}, category={self.category}, "
            f"limit={self.limit}, period={self.period})>"
        )
