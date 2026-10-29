"""
Authentication API routes.
Provides endpoints for account registration, login, and account information.
"""
from typing import List

from fastapi import APIRouter, Depends, HTTPException, status
from sqlalchemy.orm import Session

from apps.accounts.models import Account
from apps.accounts.schemas import (
    AccountCreate,
    AccountResponse,
    AccountUpdate,
    AccountCurrencyConversionRequest,
    AccountCurrencyConversionResponse,
)
from apps.accounts.services import AccountService
from apps.transactions.schemas import TransactionResponse
from apps.users.models import User
from apps.users.routes import get_current_user, get_db

router = APIRouter(prefix="/accounts", tags=["Accounts"])


def get_account_or_404(account_id: int, user_id: int, db: Session) -> Account:
    account = (
        db.query(Account)
        .filter(Account.id == account_id, Account.user_id == user_id)
        .first()
    )
    if not account:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND, detail="Account not found"
        )
    return account


@router.post(
    "/create",
    response_model=AccountResponse,
    status_code=status.HTTP_201_CREATED,
)
def create_account(
    data: AccountCreate,
    current_user: User = Depends(get_current_user),
    db: Session = Depends(get_db),
) -> AccountResponse:
    """Register a new account for the authenticated user."""
    account = Account(
        user_id=current_user.id, name=data.name, currency=data.currency
    )
    db.add(account)
    db.commit()
    db.refresh(account)
    return account


@router.get("/", response_model=List[AccountResponse])
def list_accounts(
    current_user: User = Depends(get_current_user),
    db: Session = Depends(get_db),
) -> List[AccountResponse]:
    """List all accounts for the authenticated user."""
    accounts = (
        db.query(Account).filter(Account.user_id == current_user.id).all()
    )
    return accounts


@router.get("/{account_id}", response_model=AccountResponse)
def get_account(
    account_id: int,
    current_user: User = Depends(get_current_user),
    db: Session = Depends(get_db),
) -> AccountResponse:
    """Get a single account owned by the authenticated user."""
    account = get_account_or_404(account_id, current_user.id, db)
    return account


@router.put("/{account_id}", response_model=AccountResponse)
def update_account(
    account_id: int,
    data: AccountUpdate,
    current_user: User = Depends(get_current_user),
    db: Session = Depends(get_db),
) -> AccountResponse:
    """Update account details for the authenticated user."""
    account = get_account_or_404(account_id, current_user.id, db)

    if data.name is None and data.is_active is None:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="At least one field must be provided for update",
        )

    if data.name is not None:
        account.name = data.name
    if data.is_active is not None:
        account.is_active = data.is_active

    db.commit()
    db.refresh(account)
    return account


@router.post(
    "/{account_id}/convert-currency",
    response_model=AccountCurrencyConversionResponse,
    status_code=status.HTTP_200_OK,
)
def convert_account_currency(
    account_id: int,
    payload: AccountCurrencyConversionRequest,
    current_user: User = Depends(get_current_user),
    db: Session = Depends(get_db),
) -> AccountCurrencyConversionResponse:
    """Convert the entire account balance into another currency."""
    return AccountService.convert_currency(
        account_id=account_id,
        user_id=current_user.id,
        target_currency=payload.target_currency,
        db=db,
    )


@router.delete("/{account_id}")
def delete_account(
    account_id: int,
    current_user: User = Depends(get_current_user),
    db: Session = Depends(get_db),
) -> dict:
    """Deactivate an account owned by the authenticated user."""
    account = get_account_or_404(account_id, current_user.id, db)
    account.is_active = False
    db.commit()
    return {"detail": "Account deactivated successfully"}
