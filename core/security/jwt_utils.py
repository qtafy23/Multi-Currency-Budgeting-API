"""
JWT token utilities for creating and verifying JWT tokens.
Provides a clean interface for token operations with support for different token types.
"""
from datetime import datetime, timedelta, timezone
from typing import Optional, Dict, Any
from jose import JWTError, jwt
from core.config.settings import settings


def create_token(
    data: Dict[str, Any],
    expires_delta: Optional[timedelta] = None,
    token_type: str = "access"
) -> str:
    """
    Create a JWT token with the provided data.

    Args:
        data: Payload data to encode in token
        expires_delta: Optional custom expiration time
        token_type: Type of token (access, refresh, etc.) for extensibility

    Returns:
        Encoded JWT token
    """
    to_encode = data.copy()

    if expires_delta:
        expire = datetime.now(timezone.utc) + expires_delta
    else:
        if token_type == "refresh":
            expire = datetime.now(timezone.utc) + timedelta(
                days=settings.refresh_token_expire_days
            )
        else:
            expire = datetime.now(timezone.utc) + timedelta(
                minutes=settings.access_token_expire_minutes
            )

    to_encode.update({
        "exp": expire,
        "type": token_type
    })

    encoded_jwt = jwt.encode(
        to_encode,
        settings.secret_key,
        algorithm=settings.algorithm
    )
    return encoded_jwt


def create_access_token(data: Dict[str, Any], expires_delta: Optional[timedelta] = None) -> str:
    """
    Create an access token.

    Args:
        data: Payload data
        expires_delta: Optional custom expiration time

    Returns:
        Encoded access token
    """
    return create_token(data, expires_delta, token_type="access")


def create_refresh_token(data: Dict[str, Any]) -> str:
    """
    Create a refresh token.

    Args:
        data: Payload data

    Returns:
        Encoded refresh token
    """
    return create_token(data, token_type="refresh")


def verify_token(token: str, token_type: str = "access") -> Optional[Dict[str, Any]]:
    """
    Verify and decode a JWT token.

    Args:
        token: Token to verify
        token_type: Expected token type

    Returns:
        Decoded payload if valid, None if invalid

    Raises:
        JWTError: If token is invalid
    """
    try:
        payload = jwt.decode(
            token,
            settings.secret_key,
            algorithms=[settings.algorithm]
        )

        # Verify token type matches
        if payload.get("type") != token_type:
            return None

        return payload
    except JWTError:
        return None


def get_user_id_from_token(token: str) -> Optional[int]:
    """
    Extract user ID from a token.

    Args:
        token: JWT token

    Returns:
        User ID if token is valid, None otherwise
    """
    payload = verify_token(token)
    if payload:
        return payload.get("sub")
    return None
