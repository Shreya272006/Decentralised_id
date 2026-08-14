"""
Shared FastAPI dependencies — primarily JWT-based authentication that
resolves the calling `Principal` (user id + role) used by every
protected route and by the RBAC layer.
"""
from dataclasses import dataclass

import jwt
from fastapi import Depends, HTTPException, Request, status
from fastapi.security import HTTPAuthorizationCredentials, HTTPBearer
from sqlalchemy.orm import Session

from app.core.security import decode_token
from app.db.session import get_db

bearer_scheme = HTTPBearer(auto_error=False)


@dataclass
class Principal:
    user_id: str
    role: str
    email: str | None = None


def get_current_principal(
    request: Request,
    credentials: HTTPAuthorizationCredentials | None = Depends(bearer_scheme),
    db: Session = Depends(get_db),
) -> Principal:
    if credentials is None:
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="Missing authentication credentials.",
            headers={"WWW-Authenticate": "Bearer"},
        )
    token = credentials.credentials
    try:
        payload = decode_token(token)
    except jwt.ExpiredSignatureError:
        raise HTTPException(status_code=status.HTTP_401_UNAUTHORIZED, detail="Token has expired.")
    except jwt.PyJWTError:
        raise HTTPException(status_code=status.HTTP_401_UNAUTHORIZED, detail="Invalid authentication token.")

    if payload.get("type") != "access":
        raise HTTPException(status_code=status.HTTP_401_UNAUTHORIZED, detail="Invalid token type.")

    from app.models.user import User  # local import avoids circular import

    user = db.query(User).filter(User.id == payload["sub"]).first()
    if user is None or not user.is_active or user.is_blocked:
        raise HTTPException(status_code=status.HTTP_401_UNAUTHORIZED, detail="Account is not active.")

    # Used by rate limiter to key on authenticated user id instead of IP.
    request.state.user_id = str(user.id)

    return Principal(user_id=str(user.id), role=user.role, email=user.email)


def get_optional_principal(
    request: Request,
    credentials: HTTPAuthorizationCredentials | None = Depends(bearer_scheme),
    db: Session = Depends(get_db),
) -> Principal | None:
    if credentials is None:
        return None
    try:
        return get_current_principal(request, credentials, db)
    except HTTPException:
        return None
