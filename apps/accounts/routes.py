"""
Authentication API routes.
Provides endpoints for account registration, login, and account information.
"""
from apps.accounts.models import Account
from apps.users import routes
from apps.users.models.users import User
from apps.users.routes import get_current_user, get_db
from core.db import db
from fastapi import APIRouter, Depends, HTTPException, status
from sqlalchemy.orm import Session
from apps.accounts.schemas import AccountCreate, AccountResponse

router = APIRouter(prefix="/accounts", tags=["Accounts"])

@router.post(
        "/create",
        response_model=AccountResponse,
        status_code=status.HTTP_201_CREATED
)
def create_account(
    data: AccountCreate,
    current_user: User = Depends(get_current_user),
    db: Session = Depends(get_db)
) -> AccountResponse:
    """
    Register a new account for the authenticated user.
    """
    account = Account(
    user_id=current_user.id,
    name=data.name,
    currency=data.currency
)
    db.add(account)
    db.commit()
    db.refresh(account)
    return account
