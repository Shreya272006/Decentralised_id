import secrets
import uuid
from datetime import datetime, timedelta, timezone

import pyotp
from fastapi import APIRouter, Depends, HTTPException, Request, Response, status
from sqlalchemy.orm import Session

from app.core.config import settings
from app.core.rate_limit import limiter
from app.core.security import (
    create_access_token,
    create_refresh_token,
    decode_token,
    encrypt_field,
    hash_password,
    verify_password,
)
from app.db.session import get_db
from app.models.did import DIDProfile
from app.models.user import IssuerProfile, User
from app.schemas.auth import (
    LoginRequest,
    LoginResponse,
    LogoutRequest,
    RefreshRequest,
    RegisterRequest,
    RegisterResponse,
    TokenResponse,
    VerifyOtpRequest,
)
from app.services.audit.logger import log_event

router = APIRouter(prefix="/auth", tags=["auth"])

MAX_FAILED_ATTEMPTS = 5
LOCKOUT_MINUTES = 15

# In-memory OTP challenge store keyed by challenge token. In production
# this belongs in Redis with a TTL matching OTP_CHALLENGE_TTL.
_otp_challenges: dict[str, dict] = {}
OTP_CHALLENGE_TTL_SECONDS = 300


def _client_ip(request: Request) -> str:
    return request.client.host if request.client else "unknown"


@router.post("/register", response_model=RegisterResponse, status_code=status.HTTP_201_CREATED)
@limiter.limit(settings.RATE_LIMIT_AUTH)
def register(request: Request, payload: RegisterRequest, db: Session = Depends(get_db)):
    existing = db.query(User).filter(User.email == payload.email).first()
    if existing:
        # Generic message — never reveal whether an email is registered.
        raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail="Registration could not be completed.")

    user = User(
        id=uuid.uuid4(),
        email=payload.email,
        hashed_password=hash_password(payload.password),
        full_name_encrypted=encrypt_field(payload.full_name),
        role=payload.role,
        is_active=True,
        is_verified=False,
    )
    db.add(user)
    db.flush()

    if payload.role == "issuer":
        db.add(
            IssuerProfile(
                id=uuid.uuid4(),
                user_id=user.id,
                organization_name=payload.full_name,
                is_approved=False,
            )
        )

    # Every new user gets a DID with a server-generated keypair for MVP
    # simplicity. In a fuller implementation the client generates the
    # keypair locally and only the public key is ever sent to the server.
    from cryptography.hazmat.primitives.asymmetric.ed25519 import Ed25519PrivateKey
    from cryptography.hazmat.primitives import serialization

    private_key = Ed25519PrivateKey.generate()
    public_pem = private_key.public_key().public_bytes(
        encoding=serialization.Encoding.PEM, format=serialization.PublicFormat.SubjectPublicKeyInfo
    ).decode()
    did_value = f"did:key:z{uuid.uuid4().hex}"

    db.add(
        DIDProfile(
            id=uuid.uuid4(),
            user_id=user.id,
            did=did_value,
            public_key_pem=public_pem,
            key_algorithm="Ed25519",
            did_document={"id": did_value, "verificationMethod": [{"publicKeyPem": public_pem}]},
        )
    )

    log_event(
        db, actor_id=str(user.id), action="user.register", resource_type="user",
        resource_id=str(user.id), ip_address=_client_ip(request), details={"role": payload.role},
    )
    db.commit()

    return RegisterResponse(user_id=user.id, email=user.email, role=user.role, mfa_setup_required=True)


@router.post("/login", response_model=LoginResponse)
@limiter.limit(settings.RATE_LIMIT_AUTH)
def login(request: Request, response: Response, payload: LoginRequest, db: Session = Depends(get_db)):
    user = db.query(User).filter(User.email == payload.email).first()

    generic_error = HTTPException(status_code=status.HTTP_401_UNAUTHORIZED, detail="Invalid email or password.")

    if user is None:
        raise generic_error

    if user.locked_until and user.locked_until > datetime.now(timezone.utc):
        raise HTTPException(
            status_code=status.HTTP_423_LOCKED,
            detail=f"Account temporarily locked due to repeated failed attempts. Try again later.",
        )

    if not verify_password(payload.password, user.hashed_password):
        user.failed_login_attempts += 1
        if user.failed_login_attempts >= MAX_FAILED_ATTEMPTS:
            user.locked_until = datetime.now(timezone.utc) + timedelta(minutes=LOCKOUT_MINUTES)
            log_event(
                db, actor_id=str(user.id), action="user.account_locked", resource_type="user",
                resource_id=str(user.id), ip_address=_client_ip(request),
            )
        db.commit()
        raise generic_error

    if not user.is_active or user.is_blocked:
        raise HTTPException(status_code=status.HTTP_403_FORBIDDEN, detail="Account is not active.")

    user.failed_login_attempts = 0
    user.locked_until = None
    db.commit()

    if user.mfa_enabled:
        challenge_token = secrets.token_urlsafe(32)
        _otp_challenges[challenge_token] = {
            "user_id": str(user.id),
            "expires_at": datetime.now(timezone.utc) + timedelta(seconds=OTP_CHALLENGE_TTL_SECONDS),
        }
        log_event(
            db, actor_id=str(user.id), action="user.login_otp_challenge", resource_type="user",
            resource_id=str(user.id), ip_address=_client_ip(request),
        )
        return LoginResponse(otp_required=True, otp_challenge_token=challenge_token)

    access_token = create_access_token(subject=str(user.id), role=user.role)
    refresh_token = create_refresh_token(subject=str(user.id))
    log_event(
        db, actor_id=str(user.id), action="user.login_success", resource_type="user",
        resource_id=str(user.id), ip_address=_client_ip(request),
    )
    db.commit()

    csrf_token = secrets.token_hex(32)
    response.set_cookie(
        key="access_token",
        value=access_token,
        httponly=True,
        secure=settings.ENVIRONMENT == "production",
        samesite="strict",
        max_age=settings.ACCESS_TOKEN_EXPIRE_MINUTES * 60,
    )
    response.set_cookie(
        key="refresh_token",
        value=refresh_token,
        httponly=True,
        secure=settings.ENVIRONMENT == "production",
        samesite="strict",
        max_age=settings.REFRESH_TOKEN_EXPIRE_DAYS * 24 * 3600,
    )
    response.set_cookie(
        key="csrf_token",
        value=csrf_token,
        httponly=False,  # Accessible by frontend JS
        secure=settings.ENVIRONMENT == "production",
        samesite="strict",
        max_age=settings.ACCESS_TOKEN_EXPIRE_MINUTES * 60,
    )

    return LoginResponse(
        otp_required=False,
        user_id=user.id,
        email=user.email,
        role=user.role,
    )


@router.post("/verify-otp", response_model=TokenResponse)
@limiter.limit(settings.RATE_LIMIT_AUTH)
def verify_otp(request: Request, response: Response, payload: VerifyOtpRequest, db: Session = Depends(get_db)):
    challenge = _otp_challenges.get(payload.otp_challenge_token)
    if not challenge or challenge["expires_at"] < datetime.now(timezone.utc):
        _otp_challenges.pop(payload.otp_challenge_token, None)
        raise HTTPException(status_code=status.HTTP_401_UNAUTHORIZED, detail="OTP challenge expired or invalid.")

    user = db.query(User).filter(User.id == challenge["user_id"]).first()
    if user is None or not user.mfa_secret_encrypted:
        raise HTTPException(status_code=status.HTTP_401_UNAUTHORIZED, detail="MFA is not configured for this account.")

    from app.core.security import decrypt_field

    totp = pyotp.TOTP(decrypt_field(user.mfa_secret_encrypted))
    if not totp.verify(payload.otp_code, valid_window=settings.OTP_VALID_WINDOW):
        raise HTTPException(status_code=status.HTTP_401_UNAUTHORIZED, detail="Invalid one-time passcode.")

    _otp_challenges.pop(payload.otp_challenge_token, None)

    access_token = create_access_token(subject=str(user.id), role=user.role)
    refresh_token = create_refresh_token(subject=str(user.id))

    log_event(
        db, actor_id=str(user.id), action="user.login_otp_success", resource_type="user",
        resource_id=str(user.id), ip_address=_client_ip(request),
    )
    db.commit()

    csrf_token = secrets.token_hex(32)
    response.set_cookie(
        key="access_token",
        value=access_token,
        httponly=True,
        secure=settings.ENVIRONMENT == "production",
        samesite="strict",
        max_age=settings.ACCESS_TOKEN_EXPIRE_MINUTES * 60,
    )
    response.set_cookie(
        key="refresh_token",
        value=refresh_token,
        httponly=True,
        secure=settings.ENVIRONMENT == "production",
        samesite="strict",
        max_age=settings.REFRESH_TOKEN_EXPIRE_DAYS * 24 * 3600,
    )
    response.set_cookie(
        key="csrf_token",
        value=csrf_token,
        httponly=False,
        secure=settings.ENVIRONMENT == "production",
        samesite="strict",
        max_age=settings.ACCESS_TOKEN_EXPIRE_MINUTES * 60,
    )

    return TokenResponse(
        expires_in=settings.ACCESS_TOKEN_EXPIRE_MINUTES * 60,
        user_id=user.id,
        email=user.email,
        role=user.role,
    )


@router.post("/refresh", response_model=TokenResponse)
@limiter.limit(settings.RATE_LIMIT_AUTH)
def refresh(request: Request, response: Response, payload: RefreshRequest, db: Session = Depends(get_db)):
    ref_token = payload.refresh_token or request.cookies.get("refresh_token")
    if not ref_token:
        raise HTTPException(status_code=status.HTTP_401_UNAUTHORIZED, detail="Missing refresh token.")
    try:
        claims = decode_token(ref_token)
    except Exception:
        raise HTTPException(status_code=status.HTTP_401_UNAUTHORIZED, detail="Invalid refresh token.")

    if claims.get("type") != "refresh":
        raise HTTPException(status_code=status.HTTP_401_UNAUTHORIZED, detail="Invalid token type.")

    user = db.query(User).filter(User.id == claims["sub"]).first()
    if user is None or not user.is_active or user.is_blocked:
        raise HTTPException(status_code=status.HTTP_401_UNAUTHORIZED, detail="Account is not active.")

    access_token = create_access_token(subject=str(user.id), role=user.role)
    new_refresh_token = create_refresh_token(subject=str(user.id))

    csrf_token = secrets.token_hex(32)
    response.set_cookie(
        key="access_token",
        value=access_token,
        httponly=True,
        secure=settings.ENVIRONMENT == "production",
        samesite="strict",
        max_age=settings.ACCESS_TOKEN_EXPIRE_MINUTES * 60,
    )
    response.set_cookie(
        key="refresh_token",
        value=new_refresh_token,
        httponly=True,
        secure=settings.ENVIRONMENT == "production",
        samesite="strict",
        max_age=settings.REFRESH_TOKEN_EXPIRE_DAYS * 24 * 3600,
    )
    response.set_cookie(
        key="csrf_token",
        value=csrf_token,
        httponly=False,
        secure=settings.ENVIRONMENT == "production",
        samesite="strict",
        max_age=settings.ACCESS_TOKEN_EXPIRE_MINUTES * 60,
    )

    return TokenResponse(
        expires_in=settings.ACCESS_TOKEN_EXPIRE_MINUTES * 60,
        user_id=user.id,
        email=user.email,
        role=user.role,
    )


@router.post("/logout", status_code=status.HTTP_204_NO_CONTENT)
def logout(request: Request, response: Response, payload: LogoutRequest = None, db: Session = Depends(get_db)):
    # Clear cookies
    response.delete_cookie("access_token")
    response.delete_cookie("refresh_token")
    response.delete_cookie("csrf_token")
    return None
