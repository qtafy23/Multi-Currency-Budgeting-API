from sqlalchemy import Column, Integer, String, DateTime, Boolean
from datetime import datetime, timezone
from core.db import Base
from core.security import hash_password, verify_password


class User(Base):
    __tablename__ = "users"

    id = Column(Integer, primary_key=True, index=True)
    email = Column(String, nullable=False, unique=True, index=True)
    hashed_password = Column(String, nullable=False)
    is_active = Column(Boolean, default=True)
    is_verified = Column(Boolean, default=False)  # For email verification extension
    created_at = Column(DateTime, default=lambda: datetime.now(timezone.utc))
    updated_at = Column(DateTime, default=lambda: datetime.now(timezone.utc), onupdate=lambda: datetime.now(timezone.utc))

    def set_password(self, password: str) -> None:
        """Hash and set the user's password."""
        self.hashed_password = hash_password(password)

    def verify_password(self, password: str) -> bool:
        """Verify a plain password against the stored hashed password."""
        return verify_password(password, self.hashed_password)

    def __repr__(self) -> str:
        return f"<User(id={self.id}, email={self.email})>"
