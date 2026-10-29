from decimal import Decimal, ROUND_HALF_UP

from fastapi import HTTPException, status
from sqlalchemy.orm import Session

from apps.accounts.models import Account, AccountEvent
from apps.exchange.services import ExchangeRateService
from apps.transactions.models import Transaction
from apps.users.models import User
from core.constants.currency import Currency
from core.constants.transaction import TransactionType


class AccountService:
    """Business logic for account operations."""

    @staticmethod
    def convert_currency(
        account_id: int,
        user_id: int,
        target_currency: Currency,
        db: Session,
    ) -> Transaction:
        account = (
            db.query(Account)
            .filter(
                Account.id == account_id,
                Account.user_id == user_id,
                Account.is_active.is_(True),
            )
            .with_for_update()
            .first()
        )

        if not account:
            raise HTTPException(
                status_code=status.HTTP_404_NOT_FOUND,
                detail="Account not found or inactive",
            )

        source_currency = Currency(account.currency)

        if source_currency == target_currency:
            raise HTTPException(
                status_code=status.HTTP_400_BAD_REQUEST,
                detail="Account already uses the target currency",
            )

        old_balance = Decimal(str(account.balance or 0))

        if old_balance == Decimal("0.00"):
            event = AccountEvent(
                account_id=account.id,
                event_type="currency_changed",
                old_currency=source_currency.value,
                new_currency=target_currency.value,
                details={
                    "balance": "0.00",
                    "reason": "zero_balance_currency_change",
                },
            )

            account.currency = target_currency.value
            db.add(event)

            try:
                db.commit()
                db.refresh(account)
            except Exception:
                db.rollback()
                raise

            return {
                "account": account,
                "transaction": None,
                "event_id": event.id,
                "converted": False,
            }

        try:
            exchange_rate = ExchangeRateService.get_rate(
                db, source_currency, target_currency
            )

            rate = Decimal(str(exchange_rate.rate))
            old_balance = Decimal(str(account.balance or 0))

            new_balance = (old_balance * rate).quantize(
                Decimal("0.01"),
                rounding=ROUND_HALF_UP,
            )

            # Update the account and preserve the conversion history.
            account.balance = new_balance
            account.currency = target_currency.value

            transaction = Transaction(
                account_id=account.id,
                type=TransactionType.CONVERSION,
                original_amount=old_balance,
                converted_amount=new_balance,
                original_currency=source_currency,
                account_currency=target_currency,
                exchange_rate=rate,
                amount=new_balance,
                balance_after=new_balance,
                currency=target_currency.value,
                note=(
                    f"Currency conversion: "
                    f"{source_currency.value} -> "
                    f"{target_currency.value}"
                ),
            )

            db.add(transaction)
            db.commit()
            db.refresh(transaction)
            db.refresh(account)

            return {
                "account": account,
                "transaction": transaction,
                "event_id": None,
                "converted": True,
            }

        except Exception:
            db.rollback()
            raise
