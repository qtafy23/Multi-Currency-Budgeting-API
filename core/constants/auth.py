"""
Constants used across the authentication module.
Centralized constants for better maintainability and consistency.
"""
from core.config.settings import settings

# Token expiration times (in seconds)
ACCESS_TOKEN_EXPIRE_SECONDS = settings.access_token_expire_minutes * 60
REFRESH_TOKEN_EXPIRE_SECONDS = settings.refresh_token_expire_days * 24 * 60 * 60

# Password requirements
MIN_PASSWORD_LENGTH = 8

# Error messages
ERROR_INVALID_CREDENTIALS = "Invalid credentials"
ERROR_USER_ALREADY_EXISTS = "User with email {email} already exists"
ERROR_USER_INACTIVE = "User account is inactive"
ERROR_INVALID_TOKEN = "Invalid or expired token"
ERROR_USER_NOT_FOUND = "User not found or inactive"
ERROR_DB_CONSTRAINT = "Failed to register user due to database constraint"

# Success messages
MSG_USER_REGISTERED = "User registered successfully"
MSG_LOGIN_SUCCESSFUL = "Login successful"
MSG_EMAIL_VERIFIED = "Email verified successfully"
MSG_PASSWORD_CHANGED = "Password changed successfully"
MSG_LOGOUT_SUCCESSFUL = "Logged out successfully"

# Token types
TOKEN_TYPE_BEARER = "bearer"
TOKEN_TYPE_ACCESS = "access"
TOKEN_TYPE_REFRESH = "refresh"
