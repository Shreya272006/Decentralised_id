"""
Centralized application configuration.
All secrets are loaded from environment variables — never hardcoded.
"""
from functools import lru_cache
from typing import List

from pydantic_settings import BaseSettings, SettingsConfigDict


class Settings(BaseSettings):
    model_config = SettingsConfigDict(env_file=".env", env_file_encoding="utf-8", extra="ignore")

    # --- Core ---
    APP_NAME: str = "Decentralized AI Identity Verification"
    ENVIRONMENT: str = "development"
    DEBUG: bool = False
    API_V1_PREFIX: str = "/api"

    DATABASE_URL: str = "mongodb://localhost:27017/did_platform"

    # --- Redis (rate limiting / OTP / session cache) ---
    REDIS_URL: str = "redis://localhost:6379/0"

    # --- JWT ---
    JWT_SECRET_KEY: str
    JWT_ALGORITHM: str = "HS256"
    ACCESS_TOKEN_EXPIRE_MINUTES: int = 30
    REFRESH_TOKEN_EXPIRE_DAYS: int = 7

    # --- Field-level encryption (AES-256-GCM) ---
    # 32-byte base64/hex encoded key. Rotate via key-versioning in production.
    FIELD_ENCRYPTION_KEY: str

    # --- OTP ---
    OTP_ISSUER_NAME: str = "DecentraID"
    OTP_VALID_WINDOW: int = 1

    # --- CORS ---
    ALLOWED_ORIGINS: List[str] = ["http://localhost:3000"]

    # --- Rate limiting ---
    RATE_LIMIT_DEFAULT: str = "100/minute"
    RATE_LIMIT_AUTH: str = "10/minute"
    RATE_LIMIT_AI: str = "20/minute"
    RATE_LIMIT_VERIFY: str = "30/minute"

    # --- Blockchain ---
    WEB3_PROVIDER_URL: str = "http://localhost:8545"
    CHAIN_ID: int = 31337
    DEPLOYER_PRIVATE_KEY: str = ""
    CREDENTIAL_REGISTRY_ADDRESS: str = ""
    REVOCATION_REGISTRY_ADDRESS: str = ""
    ISSUER_REGISTRY_ADDRESS: str = ""

    # --- AI thresholds ---
    FACE_MATCH_THRESHOLD: float = 0.72
    FRAUD_REVIEW_THRESHOLD: float = 0.45
    FRAUD_REJECT_THRESHOLD: float = 0.75

    # --- File uploads ---
    MAX_UPLOAD_MB: int = 8
    UPLOAD_DIR: str = "/tmp/did_uploads"


@lru_cache
def get_settings() -> "Settings":
    return Settings()


settings = get_settings()
