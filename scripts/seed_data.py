"""Insert deterministic demo data into development or testing databases."""
from datetime import datetime, timezone
from decimal import Decimal

from sqlalchemy.engine import make_url
from sqlalchemy.orm import Session

from apps.accounts.models import Account
from apps.budgets.models import Budget
from apps.users.models import User
from core.config.settings import settings
from core.constants.budgets import BudgetPeriod
from core.db.db import SessionLocal

DEMO_EMAIL = "demo@example.com"
DEMO_PASSWORD = "dev-only-password"

ACCOUNTS = (
    {
        "name": "Everyday account",
        "balance": Decimal("2840.50"),
        "currency": "USD",
    },
    {
        "name": "Travel savings",
        "balance": Decimal("900.00"),
        "currency": "EUR",
    },
)

BUDGETS = (
    {
        "category": "groceries",
        "limit": Decimal("600.00"),
        "spent_amount": Decimal("245.30"),
    },
    {
        "category": "transport",
        "limit": Decimal("180.00"),
        "spent_amount": Decimal("72.50"),
    },
)


def validate_seed_target(environment: str, database_url: str) -> None:
    """
    Reject seed runs unless
    environment and database match a local dev/test pair.
    """
    expected_databases = {
        "development": "mcb_dev",
        "testing": "mcb_test",
    }
    expected_database = expected_databases.get(environment.lower())
    if expected_database is None:
        raise RuntimeError(
            "Seed is allowed only in development or testing environments"
        )

    url = make_url(database_url)
    if url.get_backend_name() != "postgresql":
        raise RuntimeError(
            "Seed requires a local PostgreSQL development or test database"
        )
    if url.database != expected_database:
        raise RuntimeError(
            f"ENV={environment} must use database {
                expected_database!r}; refusing to seed"
        )
    if url.host not in {"db", "localhost", "127.0.0.1"}:
        raise RuntimeError(
            "Seed is allowed only against the local Compose database"
        )


def seed_demo_data(db: Session) -> dict[str, int]:
    """Create missing demo records without changing existing records."""
    created = {"users": 0, "accounts": 0, "budgets": 0}

    user = db.query(User).filter(User.email == DEMO_EMAIL).first()
    if user is None:
        user = User(email=DEMO_EMAIL, is_active=True, is_verified=True)
        user.set_password(DEMO_PASSWORD)
        db.add(user)
        db.flush()
        created["users"] += 1

    now = datetime.now(timezone.utc)
    for values in ACCOUNTS:
        account = (
            db.query(Account)
            .filter(
                Account.user_id == user.id,
                Account.name == values["name"],
            )
            .first()
        )
        if account is None:
            db.add(
                Account(
                    user_id=user.id,
                    is_active=True,
                    created_at=now,
                    updated_at=now,
                    **values,
                )
            )
            created["accounts"] += 1

    for values in BUDGETS:
        budget = (
            db.query(Budget)
            .filter(
                Budget.user_id == user.id,
                Budget.category == values["category"],
                Budget.period == BudgetPeriod.MONTHLY,
            )
            .first()
        )
        if budget is None:
            db.add(
                Budget(
                    user_id=user.id,
                    period=BudgetPeriod.MONTHLY,
                    **values,
                )
            )
            created["budgets"] += 1

    db.flush()
    return created


def main() -> None:
    validate_seed_target(settings.env, settings.database_url)
    db = SessionLocal()
    try:
        created = seed_demo_data(db)
        db.commit()
        summary = ", ".join(
            f"{count} {name}" for name, count in created.items()
        )
        print(f"Demo seed complete: created {summary}.")
        print(f"Demo login: {DEMO_EMAIL} / {DEMO_PASSWORD}")
    except Exception:
        db.rollback()
        raise
    finally:
        db.close()


if __name__ == "__main__":
    main()
