"""
Role-Based Access Control (RBAC).

Roles are strictly enumerated; every protected endpoint declares the
roles allowed to call it via `require_roles(...)`. Object-level checks
(IDOR prevention) are performed separately in each route by comparing
the resource owner id against the authenticated principal — role
membership alone is never sufficient to authorize access to another
user's resource.
"""
from enum import Enum
from typing import Iterable

from fastapi import Depends, HTTPException, status

from app.api.deps import get_current_principal, Principal


class Role(str, Enum):
    USER = "user"
    ISSUER = "issuer"
    VERIFIER = "verifier"
    ADMIN = "admin"


def require_roles(*allowed: Role):
    """
    FastAPI dependency factory. Usage:
        @router.get("/admin/x", dependencies=[Depends(require_roles(Role.ADMIN))])
    """
    allowed_values = {r.value for r in allowed}

    def _dependency(principal: Principal = Depends(get_current_principal)) -> Principal:
        if principal.role not in allowed_values:
            raise HTTPException(
                status_code=status.HTTP_403_FORBIDDEN,
                detail="You do not have permission to perform this action.",
            )
        return principal

    return _dependency


def assert_owner_or_role(principal: Principal, resource_owner_id: str, *elevated_roles: Role):
    """
    Enforces object-level authorization: the caller must either own the
    resource or hold one of the elevated roles (e.g. ADMIN). Prevents IDOR.
    """
    elevated = {r.value for r in elevated_roles}
    if principal.user_id != str(resource_owner_id) and principal.role not in elevated:
        raise HTTPException(
            status_code=status.HTTP_403_FORBIDDEN,
            detail="You do not have access to this resource.",
        )
