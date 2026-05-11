from decimal import Decimal
from typing import List

from fastapi import APIRouter, Depends, HTTPException, status
from sqlalchemy.orm import Session

from apps.accounts.models import Account
from apps.transactions.models import Transaction, TransactionType
from apps.transactions.schemas import TransactionCreate, TransactionResponse
from apps.users.models.users import User
from apps.users.routes import get_current_user, get_db

router = APIRouter(prefix="/transactions", tags=["Transactions"])


def get_account_for_user(account_id: int, user_id: int, db: Session) -> Account:
    account = db.query(Account).filter(
        Account.id == account_id,
        Account.user_id == user_id,
        Account.is_active == True
    ).with_for_update().first()
    if not account:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="Account not found or inactive"
        )
    return account


@router.post("/", response_model=TransactionResponse, status_code=status.HTTP_201_CREATED)
def create_transaction(
    payload: TransactionCreate,
    current_user: User = Depends(get_current_user),
    db: Session = Depends(get_db)
) -> TransactionResponse:
    """Create a transaction and update the account balance within a database transaction."""
    try:
        account = get_account_for_user(
            payload.account_id,
            current_user.id,
            db
        )

        if payload.type == TransactionType.INCOME:
            new_balance = Decimal(account.balance or 0) + Decimal(payload.amount)
        else:
            payload_amount = Decimal(payload.amount)

            if Decimal(account.balance or 0) < payload_amount:
                raise HTTPException(
                    status_code=status.HTTP_400_BAD_REQUEST,
                    detail="Insufficient account balance for expense transaction"
                )
            new_balance = Decimal(account.balance or 0) - payload_amount

        account.balance = new_balance

        transaction = Transaction(
            account_id=account.id,
            type=payload.type,
            amount=payload.amount,
            balance_after=new_balance,
            currency=account.currency,
            note=payload.note,
        )
        db.add(transaction)
        db.commit()
        db.refresh(transaction)
        return transaction
    except Exception:
        db.rollback()
        raise


@router.get("/", response_model=List[TransactionResponse])
def list_transactions(
    current_user: User = Depends(get_current_user),
    db: Session = Depends(get_db)
) -> List[TransactionResponse]:
    """List transactions for all active accounts of the authenticated user."""
    transactions = db.query(Transaction).join(Account).filter(
        Account.user_id == current_user.id
    ).order_by(Transaction.created_at.desc()).all()
    return transactions


@router.get("/{transaction_id}", response_model=TransactionResponse)
def get_transaction(
    transaction_id: int,
    current_user: User = Depends(get_current_user),
    db: Session = Depends(get_db)
) -> TransactionResponse:
    """Fetch a single transaction owned by the authenticated user."""
    transaction = db.query(Transaction).join(Account).filter(
        Transaction.id == transaction_id,
        Account.user_id == current_user.id
    ).first()
    if not transaction:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="Transaction not found"
        )
    return transaction
