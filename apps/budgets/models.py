from datetime import datetime, timezone
from decimal import Decimal

from sqlalchemy import Column, Integer, String, Numeric, DateTime, ForeignKey, Enum as SAEnum, UniqueConstraint
from core.constants.budgets import BudgetPeriod, BudgetStatus
from core.db import Base


class Budget(Base):
    __tablename__ = "budgets"
    __table_args__ = (
        UniqueConstraint("user_id", "category", "period", name="uq_user_category_period"),
    )

    id = Column(Integer, primary_key=True)
    user_id = Column(Integer, ForeignKey("users.id"), nullable=False, index=True)
    category = Column(String, nullable=False, index=True)
    limit = Column(Numeric(12, 2), nullable=False)
    spent_amount = Column(Numeric(12, 2), nullable=False, default=0)
    period = Column(SAEnum(BudgetPeriod), nullable=False, default=BudgetPeriod.MONTHLY)
    created_at = Column(DateTime, default=lambda: datetime.now(timezone.utc))
    updated_at = Column(
        DateTime,
        default=lambda: datetime.now(timezone.utc),
        onupdate=lambda: datetime.now(timezone.utc)
    )

    def __repr__(self) -> str:
        return (
            f"<Budget(id={self.id}, user_id={self.user_id}, category={self.category}, "
            f"limit={self.limit}, spent_amount={self.spent_amount}, period={self.period})>"
        )

    @property
    def usage_percentage(self) -> float:
        if not self.limit or self.limit == Decimal("0"):
            return 0.0
        return float(min(100, (self.spent_amount / self.limit) * Decimal("100")))

    @property
    def remaining_amount(self) -> Decimal:
        remaining = self.limit - self.spent_amount
        return remaining if remaining >= Decimal("0") else Decimal("0")

    @property
    def status(self) -> BudgetStatus:
        if self.spent_amount >= self.limit:
            return BudgetStatus.EXCEEDED
        if self.spent_amount >= (self.limit * Decimal("0.8")):
            return BudgetStatus.WARNING
        return BudgetStatus.NORMAL
