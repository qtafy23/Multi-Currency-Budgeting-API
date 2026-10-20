"""
Authentication service layer.
Handles business logic for
user authentication including registration, login, and token management.
Can be extended to support email verification, OAuth, 2FA, etc.
"""
from typing import Optional, Tuple

from sqlalchemy.exc import IntegrityError
from sqlalchemy.orm import Session

from apps.users.models import User
from apps.users.schemas import TokenResponse, UserLogin, UserRegister
from core.constants.auth import (
    ACCESS_TOKEN_EXPIRE_SECONDS,
    ERROR_DB_CONSTRAINT,
    ERROR_INVALID_CREDENTIALS,
    ERROR_INVALID_TOKEN,
    ERROR_USER_ALREADY_EXISTS,
    ERROR_USER_INACTIVE,
    ERROR_USER_NOT_FOUND,
    MSG_EMAIL_VERIFIED,
    MSG_LOGIN_SUCCESSFUL,
    MSG_PASSWORD_CHANGED,
    MSG_USER_REGISTERED,
    TOKEN_TYPE_BEARER,
)
from core.security import (
    create_access_token,
    create_refresh_token,
    get_user_id_from_token,
    verify_token,
)


class AuthenticationService:
    """
    Service for handling user authentication.
    Extensible design allows for adding email verification, OAuth, 2FA, etc.
    """

    @staticmethod
    def register_user(
        db: Session, user_data: UserRegister
    ) -> Tuple[User, str]:
        """
        Register a new user.

        Args:
            db: Database session
            user_data: User registration data

        Returns:
            Tuple of (User object, success message)

        Raises:
            ValueError: If email already exists or validation fails
        """
        # Check if user already exists
        existing_user = (
            db.query(User).filter(User.email == user_data.email).first()
        )
        if existing_user:
            raise ValueError(
                ERROR_USER_ALREADY_EXISTS.format(email=user_data.email)
            )

        try:
            # Create new user
            new_user = User(email=user_data.email)
            new_user.set_password(user_data.password)

            db.add(new_user)
            db.commit()
            db.refresh(new_user)

            return new_user, MSG_USER_REGISTERED
        except IntegrityError:
            db.rollback()
            raise ValueError(ERROR_DB_CONSTRAINT)

    @staticmethod
    def login_user(db: Session, credentials: UserLogin) -> Tuple[User, str]:
        """
        Authenticate user with email and password.

        Args:
            db: Database session
            credentials: Login credentials

        Returns:
            Tuple of (User object, success message)

        Raises:
            ValueError: If credentials are invalid
        """
        user = db.query(User).filter(User.email == credentials.email).first()

        if not user:
            raise ValueError(ERROR_INVALID_CREDENTIALS)

        if not user.verify_password(credentials.password):
            raise ValueError(ERROR_INVALID_CREDENTIALS)

        if not user.is_active:
            raise ValueError(ERROR_USER_INACTIVE)

        return user, MSG_LOGIN_SUCCESSFUL

    @staticmethod
    def create_tokens(
        user: User, include_refresh: bool = True
    ) -> TokenResponse:
        """
        Create access and optionally refresh tokens for a user.

        Args:
            user: User object
            include_refresh: Whether to include refresh token

        Returns:
            TokenResponse with access and refresh tokens
        """
        token_data = {"sub": str(user.id), "email": user.email}
        access_token = create_access_token(token_data)

        refresh_token = None
        if include_refresh:
            refresh_token = create_refresh_token(
                {
                    **token_data,
                    "refresh_token_version": user.refresh_token_version,
                }
            )

        return TokenResponse(
            access_token=access_token,
            refresh_token=refresh_token,
            token_type=TOKEN_TYPE_BEARER,
            expires_in=ACCESS_TOKEN_EXPIRE_SECONDS,
        )

    @staticmethod
    def refresh_access_token(db: Session, refresh_token: str) -> TokenResponse:
        """
        Create a new access token using a refresh token.

        Args:
            db: Database session
            refresh_token: Refresh token

        Returns:
            TokenResponse with new access token

        Raises:
            ValueError: If refresh token is invalid
        """
        # Verify refresh token
        payload = verify_token(refresh_token, token_type="refresh")
        if not payload:
            raise ValueError(ERROR_INVALID_TOKEN)

        user_id = payload.get("sub")
        if not user_id:
            raise ValueError(ERROR_INVALID_TOKEN)

        # Get user from database
        user = db.query(User).filter(User.id == user_id).first()
        if not user or not user.is_active:
            raise ValueError(ERROR_USER_NOT_FOUND)
        if (
            payload.get("refresh_token_version", 0)
            != user.refresh_token_version
        ):
            raise ValueError(ERROR_INVALID_TOKEN)

        # Create new access token
        token_data = {"sub": str(user.id), "email": user.email}
        access_token = create_access_token(token_data)

        return TokenResponse(
            access_token=access_token,
            token_type=TOKEN_TYPE_BEARER,
            expires_in=ACCESS_TOKEN_EXPIRE_SECONDS,
        )

    @staticmethod
    def get_user_by_token(db: Session, token: str) -> Optional[User]:
        """
        Get user from database using access token.

        Args:
            db: Database session
            token: Access token

        Returns:
            User object if token is valid, None otherwise
        """
        user_id = get_user_id_from_token(token)
        if not user_id:
            return None

        user = db.query(User).filter(User.id == user_id).first()
        return user if user and user.is_active else None

    @staticmethod
    def revoke_refresh_tokens(db: Session, user: User) -> None:
        """Revoke all refresh tokens issued before this logout."""
        user.refresh_token_version += 1
        db.commit()

    @staticmethod
    def verify_email(db: Session, user: User) -> Tuple[User, str]:
        """
        Mark user email as verified.
        Hook for email verification extension.

        Args:
            db: Database session
            user: User object

        Returns:
            Tuple of (User object, success message)
        """
        user.is_verified = True
        db.commit()
        db.refresh(user)
        return user, MSG_EMAIL_VERIFIED

    @staticmethod
    def change_password(
        db: Session, user: User, new_password: str
    ) -> Tuple[User, str]:
        """
        Change user password.

        Args:
            db: Database session
            user: User object
            new_password: New password

        Returns:
            Tuple of (User object, success message)
        """
        user.set_password(new_password)
        db.commit()
        db.refresh(user)
        return user, MSG_PASSWORD_CHANGED
