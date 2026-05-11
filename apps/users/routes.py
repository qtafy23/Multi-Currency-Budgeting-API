"""
Authentication API routes.
Provides endpoints for user registration, login, token refresh, and user information.
"""
from fastapi import APIRouter, Depends, HTTPException, status
from fastapi.security import OAuth2PasswordBearer, OAuth2PasswordRequestForm
from sqlalchemy.orm import Session

from apps.users.schemas import (
    UserRegister,
    UserLogin,
    TokenResponse,
    UserResponse,
    RefreshTokenRequest
)
from apps.users.services import AuthenticationService
from apps.users.models.users import User
from core.constants.auth import MSG_LOGOUT_SUCCESSFUL
from core.db import SessionLocal
from core.security import verify_token


router = APIRouter(prefix="/auth", tags=["authentication"])
oauth2_scheme = OAuth2PasswordBearer(tokenUrl="/api/v1/auth/login")


def get_db() -> Session:
    """Get database session."""
    db = SessionLocal()
    try:
        yield db
    finally:
        db.close()


def get_current_user(
    token: str = Depends(oauth2_scheme),
    db: Session = Depends(get_db)
) -> User:
    """
    Dependency to get current authenticated user from token.
    Can be extended to support different auth methods.

    Args:
        token: Authorization token from header
        db: Database session

    Returns:
        User object

    Raises:
        HTTPException: If token is invalid or user not found
    """
    user = AuthenticationService.get_user_by_token(db, token)
    if not user:
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="Invalid or expired token"
        )

    return user


@router.post("/register", response_model=UserResponse, status_code=status.HTTP_201_CREATED)
def register(
    user_data: UserRegister,
    db: Session = Depends(get_db)
) -> UserResponse:
    """
    Register a new user.

    Args:
        user_data: Registration data (email and password)
        db: Database session

    Returns:
        Created user information

    Raises:
        HTTPException: If registration fails
    """
    try:
        user, _ = AuthenticationService.register_user(db, user_data)
        return UserResponse.from_orm(user)
    except ValueError as e:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail=str(e)
        )


@router.post("/login", response_model=TokenResponse)
def login(
    form_data: OAuth2PasswordRequestForm = Depends(),
    db: Session = Depends(get_db)
) -> TokenResponse:
    """
    User login endpoint.

    Args:
        form_data: OAuth2 form data containing username(email) and password
        db: Database session

    Returns:
        Access and refresh tokens

    Raises:
        HTTPException: If credentials are invalid
    """
    try:
        credentials = UserLogin(email=form_data.username, password=form_data.password)
        user, _ = AuthenticationService.login_user(db, credentials)
        tokens = AuthenticationService.create_tokens(user, include_refresh=True)
        return tokens
    except ValueError as e:
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail=str(e)
        )


@router.post("/refresh", response_model=TokenResponse)
def refresh_token(
    request: RefreshTokenRequest,
    db: Session = Depends(get_db)
) -> TokenResponse:
    """
    Refresh access token using refresh token.

    Args:
        request: Refresh token request
        db: Database session

    Returns:
        New access token

    Raises:
        HTTPException: If refresh token is invalid
    """
    try:
        tokens = AuthenticationService.refresh_access_token(db, request.refresh_token)
        return tokens
    except ValueError as e:
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail=str(e)
        )


@router.get("/me", response_model=UserResponse)
def get_current_user_info(
    current_user: User = Depends(get_current_user)
) -> UserResponse:
    """
    Get current authenticated user information.

    Args:
        current_user: Current authenticated user from dependency

    Returns:
        User information
    """
    return UserResponse.from_orm(current_user)


@router.post("/logout")
def logout(current_user: User = Depends(get_current_user)) -> dict:
    """
    Logout endpoint (client-side token removal).
    This is a placeholder for potential server-side token blacklisting.

    Args:
        current_user: Current authenticated user

    Returns:
        Success message
    """
    return {"message": MSG_LOGOUT_SUCCESSFUL}
