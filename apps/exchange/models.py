from datetime import datetime, timezone

from sqlalchemy import (
    Column,
    DateTime,
    Enum,
    Integer,
    Numeric,
    UniqueConstraint,
)

from core.constants.currency import Currency
from core.db import Base


class ExchangeRate(Base):
    __tablename__ = "exchange_rates"
    __table_args__ = (
        UniqueConstraint(
            "from_currency", "to_currency", name="uq_exchange_rate_pair"
        ),
    )

    id = Column(Integer, primary_key=True)
    from_currency = Column(Enum(Currency), nullable=False)
    to_currency = Column(Enum(Currency), nullable=False)
    rate = Column(Numeric(18, 8), nullable=False)
    created_at = Column(DateTime, default=lambda: datetime.now(timezone.utc))
    # Last successful provider refresh in UTC, even for unchanged quotes.
    updated_at = Column(
        DateTime,
        default=lambda: datetime.now(timezone.utc).replace(tzinfo=None),
    )

    def __repr__(self) -> str:
        return (
            f"<ExchangeRate(id={self.id}, from={self.from_currency}, "
            f"to={self.to_currency}, rate={self.rate})>"
        )
