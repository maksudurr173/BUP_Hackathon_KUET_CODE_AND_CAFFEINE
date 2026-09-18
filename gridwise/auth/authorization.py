"""Role-Based Access Control (RBAC) and Authorization policies.

Ensures that permissions are strictly enforced on protected administrative
and operational actions.
"""

from enum import Enum
from typing import Set
from gridwise.app.errors import ForbiddenException


class Role(str, Enum):
    ADMIN = "admin"
    OPERATOR = "operator"
    READONLY = "readonly"


ROLE_HIERARCHY = {
    Role.ADMIN: {Role.ADMIN, Role.OPERATOR, Role.READONLY},
    Role.OPERATOR: {Role.OPERATOR, Role.READONLY},
    Role.READONLY: {Role.READONLY},
}


def verify_role_authorized(user_role: str, required_roles: Set[Role]) -> None:
    """Verifies that the user role has sufficient privileges for the operation."""
    try:
        current_role = Role(user_role.lower())
    except ValueError:
        raise ForbiddenException(f"Invalid user role '{user_role}'")

    effective_roles = ROLE_HIERARCHY.get(current_role, set())
    if not effective_roles.intersection(required_roles):
        raise ForbiddenException(
            f"Role '{user_role}' does not have required permissions: {[r.value for r in required_roles]}"
        )
