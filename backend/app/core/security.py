"""
Security primitives used across the platform:
  - Password hashing (bcrypt via passlib)
  - JWT access / refresh token issuance & verification
  - AES-256-GCM field-level encryption for sensitive PII at rest
  - Constant-time comparison helpers

No raw identity data (document scans, unmasked ID numbers, facial
embeddings) is ever persisted without passing through `encrypt_field`.
"""
import base64
import hashlib
import hmac
import os
import secrets
from datetime import datetime, timedelta, timezone
from typing import Any, Optional

import jwt
from cryptography.hazmat.primitives.ciphers.aead import AESGCM
from passlib.context import CryptContext

from app.core.config import settings

pwd_context = CryptContext(schemes=["bcrypt"], deprecated="auto", bcrypt__rounds=12)


# ---------------------------------------------------------------------------
# Password hashing
# ---------------------------------------------------------------------------
def hash_password(plain_password: str) -> str:
    return pwd_context.hash(plain_password)


def verify_password(plain_password: str, hashed_password: str) -> bool:
    return pwd_context.verify(plain_password, hashed_password)


# ---------------------------------------------------------------------------
# JWT
# ---------------------------------------------------------------------------
def create_access_token(subject: str, role: str, extra_claims: Optional[dict] = None) -> str:
    now = datetime.now(timezone.utc)
    payload = {
        "sub": subject,
        "role": role,
        "type": "access",
        "iat": now,
        "exp": now + timedelta(minutes=settings.ACCESS_TOKEN_EXPIRE_MINUTES),
        "jti": secrets.token_hex(16),
    }
    if extra_claims:
        payload.update(extra_claims)
    return jwt.encode(payload, settings.JWT_SECRET_KEY, algorithm=settings.JWT_ALGORITHM)


def create_refresh_token(subject: str) -> str:
    now = datetime.now(timezone.utc)
    payload = {
        "sub": subject,
        "type": "refresh",
        "iat": now,
        "exp": now + timedelta(days=settings.REFRESH_TOKEN_EXPIRE_DAYS),
        "jti": secrets.token_hex(16),
    }
    return jwt.encode(payload, settings.JWT_SECRET_KEY, algorithm=settings.JWT_ALGORITHM)


def decode_token(token: str) -> dict:
    """Raises jwt.PyJWTError subclasses on invalid/expired tokens."""
    return jwt.decode(token, settings.JWT_SECRET_KEY, algorithms=[settings.JWT_ALGORITHM])


# ---------------------------------------------------------------------------
# AES-256-GCM field-level encryption
# ---------------------------------------------------------------------------
def _derive_key() -> bytes:
    """
    Derive a stable 32-byte AES key from the configured secret using
    SHA-256. In production the raw key should come from a KMS/HSM and
    be rotated with a key-version prefix stored alongside ciphertext.
    """
    raw = settings.FIELD_ENCRYPTION_KEY.encode("utf-8")
    return hashlib.sha256(raw).digest()


def encrypt_field(plaintext: str) -> str:
    """
    Encrypts a sensitive string field with AES-256-GCM.
    Output format: base64(nonce || ciphertext || tag), safe for TEXT columns.
    """
    if plaintext is None:
        return None
    key = _derive_key()
    aesgcm = AESGCM(key)
    nonce = os.urandom(12)
    ct = aesgcm.encrypt(nonce, plaintext.encode("utf-8"), associated_data=None)
    return base64.b64encode(nonce + ct).decode("utf-8")


def decrypt_field(token: str) -> str:
    if token is None:
        return None
    key = _derive_key()
    aesgcm = AESGCM(key)
    raw = base64.b64decode(token)
    nonce, ct = raw[:12], raw[12:]
    pt = aesgcm.decrypt(nonce, ct, associated_data=None)
    return pt.decode("utf-8")


def mask_identifier(value: str, visible: int = 4) -> str:
    """Returns a display-safe masked version of an identifier, e.g. ****1234."""
    if not value:
        return value
    tail = value[-visible:] if len(value) > visible else value
    return "*" * max(len(value) - visible, 4) + tail


# ---------------------------------------------------------------------------
# Integrity helpers (tamper-evident audit chain)
# ---------------------------------------------------------------------------
def sha256_hex(data: bytes) -> str:
    return hashlib.sha256(data).hexdigest()


def hmac_sha256(key: bytes, data: bytes) -> str:
    return hmac.new(key, data, hashlib.sha256).hexdigest()


def constant_time_eq(a: str, b: str) -> bool:
    return hmac.compare_digest(a, b)
