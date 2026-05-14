from typing import List, Optional

from fastapi import APIRouter, Depends, Header, HTTPException, Response, status
from sqlalchemy.orm import Session

from apps.transactions.schemas import TransactionCreate, TransactionResponse
from apps.transactions.services import TransactionService
from apps.users.models.users import User
from apps.users.routes import get_current_user, get_db

router = APIRouter(prefix="/transactions", tags=["Transactions"])


@router.post("/", response_model=TransactionResponse, status_code=status.HTTP_201_CREATED)
def create_transaction(
    payload: TransactionCreate,
    response: Response,
    idempotency_key: Optional[str] = Header(None, alias="Idempotency-Key"),
    current_user: User = Depends(get_current_user),
    db: Session = Depends(get_db)
) -> TransactionResponse:
    """Create a transaction and update the account balance."""
    transaction, created = TransactionService.create_transaction(
        db,
        payload,
        current_user.id,
        idempotency_key
    )
    if not created:
        response.status_code = status.HTTP_200_OK
    return transaction


@router.get("/", response_model=List[TransactionResponse])
def list_transactions(
    current_user: User = Depends(get_current_user),
    db: Session = Depends(get_db)
) -> List[TransactionResponse]:
    """List transactions for all accounts of the authenticated user."""
    transactions = TransactionService.get_user_transactions(
        current_user.id,
        db
    )
    return transactions


@router.get("/{transaction_id}", response_model=TransactionResponse)
def get_transaction(
    transaction_id: int,
    current_user: User = Depends(get_current_user),
    db: Session = Depends(get_db)
) -> TransactionResponse:
    """Fetch a single transaction owned by the authenticated user."""
    transaction = TransactionService.get_user_transaction(
        transaction_id,
        current_user.id,
        db
    )
    return transaction
