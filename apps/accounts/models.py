from sqlalchemy import Column, Integer, String, Numeric, Boolean, DateTime, ForeignKey
from core.db import Base


class Account(Base):
    __tablename__ = "accounts"

    id = Column(Integer, primary_key=True)

    user_id = Column(
        Integer,
        ForeignKey("users.id"),
        nullable=False
    )

    name = Column(String, nullable=False)

    balance = Column(Numeric(12, 2), default=0)

    currency = Column(String, default="USD")

    is_active = Column(Boolean, default=True)

    created_at = Column(DateTime)
    updated_at = Column(DateTime)
