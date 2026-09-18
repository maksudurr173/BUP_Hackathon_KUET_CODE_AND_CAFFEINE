"""FastAPI authentication and authorization dependencies."""

from dataclasses import dataclass
from typing import Optional, Set
from fastapi import Depends, Header, Request, status
from fastapi.security import HTTPBearer, HTTPAuthorizationCredentials

from config import settings
from gridwise.app.errors import UnauthorizedException, ForbiddenException
from gridwise.auth.authentication import verify_jwt_token, verify_api_key
from gridwise.auth.authorization import Role, verify_role_authorized

security_bearer = HTTPBearer(auto_error=False)


@dataclass
class AuthenticatedUser:
    id: str
    role: str
    auth_type: str


async def get_current_user(
    request: Request,
    auth_header: Optional[HTTPAuthorizationCredentials] = Depends(security_bearer),
    x_api_key: Optional[str] = Header(None, alias="X-API-Key")
) -> AuthenticatedUser:
    """Authenticates the incoming request via JWT Bearer Token or API Key.
    
    If AUTH_ENABLED is False and no credentials are provided, returns default operator.
    If credentials ARE provided, always verifies them for security correctness.
    """
    # 1. Try Bearer JWT
    if auth_header and auth_header.credentials:
        payload = verify_jwt_token(auth_header.credentials)
        user = AuthenticatedUser(
            id=str(payload.get("sub", "unknown")),
            role=str(payload.get("role", "operator")),
            auth_type="jwt"
        )
        request.state.user = user
        return user

    # 2. Try X-API-Key
    if x_api_key:
        if verify_api_key(x_api_key):
            user = AuthenticatedUser(
                id="api_key_service",
                role="operator",
                auth_type="api_key"
            )
            request.state.user = user
            return user
        else:
            raise UnauthorizedException("Invalid API key provided in X-API-Key header")

    # 3. If Auth is NOT enforced and no credentials were supplied
    if not settings.AUTH_ENABLED:
        user = AuthenticatedUser(
            id="anonymous_local_user",
            role="operator",
            auth_type="none"
        )
        request.state.user = user
        return user

    # 4. Auth is strictly required but no valid credential was supplied
    raise UnauthorizedException("Missing authentication credentials. Please provide Bearer Token or X-API-Key")


def require_role(allowed_roles: Set[Role]):
    """Dependency generator that enforces specific roles on endpoints."""
    async def role_checker(user: AuthenticatedUser = Depends(get_current_user)) -> AuthenticatedUser:
        verify_role_authorized(user.role, allowed_roles)
        return user
    return role_checker
