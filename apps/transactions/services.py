import logging
from decimal import Decimal
from typing import Optional, Tuple

from fastapi import HTTPException, status
from sqlalchemy.exc import IntegrityError
from sqlalchemy.orm import Session

from apps.accounts.models import Account
from apps.budgets.services import BudgetService
from apps.exchange.services import ExchangeRateService
from apps.transactions.models import Transaction
from apps.transactions.schemas import TransactionCreate
from core.constants.currency import Currency
from core.constants.transaction import TransactionType

logger = logging.getLogger(__name__)


class TransactionService:
    """Service layer for transaction operations."""

    @staticmethod
    def get_user_account(
        account_id: int, user_id: int, db: Session
    ) -> Account:
        """Retrieve an active account owned by the user with a lock."""
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
        return account

    @staticmethod
    def find_idempotent_transaction(
        db: Session,
        user_id: int,
        idempotency_key: Optional[str],
    ) -> Optional[Transaction]:
        """Find an existing transaction by idempotency_key."""
        if idempotency_key is None:
            return None

        return (
            db.query(Transaction)
            .join(Account)
            .filter(
                Account.user_id == user_id,
                Transaction.idempotency_key == idempotency_key,
            )
            .first()
        )

    @staticmethod
    def validate_idempotent_request(
        existing: Transaction,
        payload: TransactionCreate,
    ) -> None:
        """Validate that the repeated request matches the original."""

        if (
            existing.account_id != payload.account_id
            or existing.type != payload.type
            or existing.original_amount != payload.amount
            or existing.original_currency != payload.currency
            or existing.category != payload.category
            or existing.note != payload.note
        ):
            raise HTTPException(
                status_code=status.HTTP_409_CONFLICT,
                detail=(
                    "Idempotency-Key has already been used "
                    "with different transaction parameters"
                ),
            )

    @staticmethod
    def calculate_new_balance(
        current_balance: Decimal,
        transaction_type: TransactionType,
        amount: Decimal,
    ) -> Decimal:
        """Calculate new balance based on transaction type."""
        if transaction_type == TransactionType.INCOME:
            return current_balance + amount

        if current_balance < amount:
            raise HTTPException(
                status_code=status.HTTP_400_BAD_REQUEST,
                detail="Insufficient account balance",
            )

        return current_balance - amount

    @staticmethod
    def create_transaction(
        db: Session,
        payload: TransactionCreate,
        user_id: int,
        idempotency_key: Optional[str],
    ) -> Tuple[Transaction, bool]:
        """
        Create a transaction with idempotent handling and balance update.
        Uses database transaction to ensure atomicity.
        Returns the transaction and a boolean flag
        indicating if it was newly created.
        """
        if payload.type == TransactionType.CONVERSION:
            raise HTTPException(
                status_code=status.HTTP_400_BAD_REQUEST,
                detail=(
                    "Use the account currency conversion endpoint "
                    "to convert an account balance"
                ),
            )

        existing = TransactionService.find_idempotent_transaction(
            db, user_id, idempotency_key
        )

        if existing:
            TransactionService.validate_idempotent_request(
                existing, payload
            )
            logger.debug(
                "Idempotency hit: user_id=%s idempotency_key=%s",
                user_id,
                idempotency_key,
            )
            return existing, False

        try:
            account = TransactionService.get_user_account(
                payload.account_id, user_id, db
            )

            current_balance = (
                Decimal(str(account.balance))
                if account.balance is not None
                else Decimal("0")
            )

            original_amount = Decimal(str(payload.amount))
            converted_amount = original_amount
            account_currency = Currency(account.currency)

            if payload.currency != account.currency:
                converted_amount = ExchangeRateService.convert_amount(
                    db, payload.currency, account_currency, original_amount
                )

            budget_warning = None
            if payload.type == TransactionType.EXPENSE and payload.category:
                budget_warning = BudgetService.get_expense_budget_warning(
                    user_id,
                    payload.category,
                    converted_amount,
                    account_currency,
                    db,
                )

            new_balance = TransactionService.calculate_new_balance(
                current_balance, payload.type, converted_amount
            )

            logger.debug(
                "Transaction calculation: account_id=%s before=%s after=%s",
                account.id,
                current_balance,
                new_balance,
            )

            account.balance = new_balance

            transaction = Transaction(
                account_id=account.id,
                idempotency_key=idempotency_key,
                type=payload.type,
                original_amount=original_amount,
                converted_amount=converted_amount,
                original_currency=payload.currency,
                account_currency=account_currency,
                amount=converted_amount,
                balance_after=new_balance,
                currency=account.currency,
                category=payload.category,
                note=payload.note,
            )
            if budget_warning:
                transaction.budget_warning = budget_warning

            db.add(transaction)
            db.commit()
            db.refresh(transaction)

            logger.debug(
                "Created transaction: id=%s account_id=%s amount=%s",
                transaction.id,
                transaction.account_id,
                transaction.amount,
            )
            return transaction, True

        except IntegrityError as exc:
            db.rollback()

            existing = TransactionService.find_idempotent_transaction(
                db, user_id, idempotency_key
            )

            if existing:
                TransactionService.validate_idempotent_request(
                    existing, payload
                )
                return existing, False

            if idempotency_key is not None:
                raise HTTPException(
                    status_code=status.HTTP_409_CONFLICT,
                    detail="Transaction conflict",
                ) from exc

            raise

    @staticmethod
    def get_user_transactions(user_id: int, db: Session) -> list[Transaction]:
        """Retrieve all transactions for user's accounts."""
        return (
            db.query(Transaction)
            .join(Account)
            .filter(Account.user_id == user_id)
            .order_by(Transaction.created_at.desc())
            .all()
        )

    @staticmethod
    def get_user_transaction(
        transaction_id: int, user_id: int, db: Session
    ) -> Transaction:
        """Retrieve a single transaction owned by user."""
        transaction = (
            db.query(Transaction)
            .join(Account)
            .filter(
                Transaction.id == transaction_id, Account.user_id == user_id
            )
            .first()
        )

        if not transaction:
            raise HTTPException(
                status_code=status.HTTP_404_NOT_FOUND,
                detail="Transaction not found",
            )

        return transaction
