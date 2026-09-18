"""Authentication utilities for JWT tokens and API keys.

Enforces server-side token validation, expiration checking, cryptographic signature
verification, and constant-time string comparisons.
"""

import hmac
import time
from datetime import datetime, timedelta, timezone
from typing import Any, Dict, Optional
import jwt

from config import settings
from gridwise.app.errors import UnauthorizedException


def create_access_token(
    subject: str,
    role: str = "operator",
    expires_delta: Optional[timedelta] = None
) -> str:
    """Creates a signed JWT access token."""
    if expires_delta:
        expire = datetime.now(timezone.utc) + expires_delta
    else:
        expire = datetime.now(timezone.utc) + timedelta(minutes=settings.JWT_ACCESS_TOKEN_EXPIRE_MINUTES)
        
    payload = {
        "sub": subject,
        "role": role,
        "exp": expire,
        "iat": datetime.now(timezone.utc)
    }
    encoded_jwt = jwt.encode(payload, settings.JWT_SECRET_KEY, algorithm=settings.JWT_ALGORITHM)
    return encoded_jwt


def verify_jwt_token(token: str) -> Dict[str, Any]:
    """Verifies and decodes a JWT access token."""
    try:
        payload = jwt.decode(
            token,
            settings.JWT_SECRET_KEY,
            algorithms=[settings.JWT_ALGORITHM]
        )
        return payload
    except jwt.ExpiredSignatureError:
        raise UnauthorizedException("Authentication token has expired")
    except jwt.InvalidTokenError:
        raise UnauthorizedException("Invalid authentication token signature or format")


def verify_api_key(provided_key: str) -> bool:
    """Verifies API Key using constant-time string comparison to prevent timing attacks."""
    if not provided_key or not settings.API_KEY_SECRET:
        return False
    return hmac.compare_digest(provided_key, settings.API_KEY_SECRET)
