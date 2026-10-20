from typing import List

from fastapi import APIRouter, Depends, HTTPException, status
from sqlalchemy.orm import Session

from apps.budgets.schemas import (
    BudgetCheckRequest,
    BudgetCheckResponse,
    BudgetCreate,
    BudgetResponse,
    BudgetStatisticsResponse,
    BudgetUpdate,
)
from apps.budgets.services import BudgetService
from apps.users.models import User
from apps.users.routes import get_current_user, get_db

router = APIRouter(prefix="/budgets", tags=["Budgets"])


@router.post(
    "/create",
    response_model=BudgetResponse,
    status_code=status.HTTP_201_CREATED,
)
def create_budget(
    payload: BudgetCreate,
    current_user: User = Depends(get_current_user),
    db: Session = Depends(get_db),
) -> BudgetResponse:
    budget = BudgetService.create_budget(current_user.id, payload, db)
    return BudgetService.serialize_budget(current_user.id, budget, db)


@router.get("/", response_model=List[BudgetResponse])
def list_budgets(
    current_user: User = Depends(get_current_user),
    db: Session = Depends(get_db),
) -> List[BudgetResponse]:
    budgets = BudgetService.get_user_budgets(current_user.id, db)
    return [
        BudgetService.serialize_budget(current_user.id, budget, db)
        for budget in budgets
    ]


@router.get("/statistics", response_model=BudgetStatisticsResponse)
def budget_statistics(
    current_user: User = Depends(get_current_user),
    db: Session = Depends(get_db),
) -> BudgetStatisticsResponse:
    stats = BudgetService.get_budget_statistics(current_user.id, db)
    return BudgetStatisticsResponse(**stats)


@router.get("/{budget_id}", response_model=BudgetResponse)
def get_budget(
    budget_id: int,
    current_user: User = Depends(get_current_user),
    db: Session = Depends(get_db),
) -> BudgetResponse:
    budget = BudgetService.get_budget_by_id(current_user.id, budget_id, db)
    return BudgetService.serialize_budget(current_user.id, budget, db)


@router.put("/{budget_id}", response_model=BudgetResponse)
def update_budget(
    budget_id: int,
    payload: BudgetUpdate,
    current_user: User = Depends(get_current_user),
    db: Session = Depends(get_db),
) -> BudgetResponse:
    if payload.limit is None and payload.currency is None:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="At least one budget field must be provided",
        )
    budget = BudgetService.update_budget(
        current_user.id, budget_id, payload, db
    )
    return BudgetService.serialize_budget(current_user.id, budget, db)


@router.delete("/{budget_id}")
def delete_budget(
    budget_id: int,
    current_user: User = Depends(get_current_user),
    db: Session = Depends(get_db),
) -> dict:
    BudgetService.delete_budget(current_user.id, budget_id, db)
    return {"detail": "Budget deleted successfully"}


@router.post("/check", response_model=List[BudgetCheckResponse])
def check_budget(
    payload: BudgetCheckRequest,
    current_user: User = Depends(get_current_user),
    db: Session = Depends(get_db),
) -> List[BudgetCheckResponse]:
    return BudgetService.check_budget_usage(
        current_user.id,
        payload.category,
        payload.amount,
        db,
        payload.period,
        payload.currency,
    )
