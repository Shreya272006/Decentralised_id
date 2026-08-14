import uuid
from datetime import datetime

from sqlalchemy import String, DateTime, ForeignKey, Boolean, Enum as SAEnum
from sqlalchemy.dialects.postgresql import UUID, JSONB
from sqlalchemy.orm import Mapped, mapped_column, relationship
import enum

from app.db.base import Base


class CredentialStatus(str, enum.Enum):
    ACTIVE = "active"
    REVOKED = "revoked"
    EXPIRED = "expired"
    SUSPENDED = "suspended"


class CredentialType(str, enum.Enum):
    AGE_VERIFICATION = "age_verification"
    STUDENT_STATUS = "student_status"
    EMPLOYEE_STATUS = "employee_status"
    KYC_VALIDITY = "kyc_validity"
    CUSTOM = "custom"


class Credential(Base):
    """
    A verifiable credential issued to a holder. `claims_encrypted` stores
    the AES-256-GCM ciphertext of the raw claim payload (e.g. exact DOB);
    only derived, non-reversible commitments are ever exposed for proofs.
    """
    __tablename__ = "credentials"

    id: Mapped[uuid.UUID] = mapped_column(UUID(as_uuid=True), primary_key=True, default=uuid.uuid4)
    holder_id: Mapped[uuid.UUID] = mapped_column(UUID(as_uuid=True), ForeignKey("users.id", ondelete="CASCADE"), index=True)
    issuer_id: Mapped[uuid.UUID] = mapped_column(UUID(as_uuid=True), ForeignKey("users.id", ondelete="RESTRICT"), index=True)

    credential_type: Mapped[str] = mapped_column(SAEnum(CredentialType, name="credential_type"), nullable=False)
    status: Mapped[str] = mapped_column(SAEnum(CredentialStatus, name="credential_status"), default=CredentialStatus.ACTIVE)

    schema_version: Mapped[str] = mapped_column(String(16), default="1.0", nullable=False)
    claims_encrypted: Mapped[str] = mapped_column(String, nullable=False)  # AES-256-GCM ciphertext, base64
    claims_commitment: Mapped[str] = mapped_column(String(128), nullable=False)  # sha256 commitment used in ZK proofs

    issuer_signature: Mapped[str] = mapped_column(String(1024), nullable=False)  # Ed25519/ECDSA sig over commitment
    signing_key_id: Mapped[str] = mapped_column(String(255), nullable=False)

    blockchain_tx_hash: Mapped[str] = mapped_column(String(66), nullable=True)
    onchain_credential_hash: Mapped[str] = mapped_column(String(66), nullable=True)  # bytes32 hex

    issued_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), default=datetime.utcnow, nullable=False)
    expires_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), nullable=True)
    revoked_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), nullable=True)
    revocation_reason: Mapped[str] = mapped_column(String(255), nullable=True)

    metadata_json: Mapped[dict] = mapped_column(JSONB, default=dict, nullable=False)

    holder: Mapped["User"] = relationship(foreign_keys=[holder_id], back_populates="credentials")
    issuer: Mapped["User"] = relationship(foreign_keys=[issuer_id])
    claims: Mapped[list["CredentialClaim"]] = relationship(back_populates="credential", cascade="all, delete-orphan")


class CredentialClaim(Base):
    """
    Individual named claim within a credential (e.g. 'date_of_birth',
    'enrollment_status'). Values are always encrypted at rest; `commitment`
    is the sha256(salt || value) commitment used for zero-knowledge proofs
    without revealing the underlying value.
    """
    __tablename__ = "credential_claims"

    id: Mapped[uuid.UUID] = mapped_column(UUID(as_uuid=True), primary_key=True, default=uuid.uuid4)
    credential_id: Mapped[uuid.UUID] = mapped_column(UUID(as_uuid=True), ForeignKey("credentials.id", ondelete="CASCADE"), index=True)

    claim_key: Mapped[str] = mapped_column(String(128), nullable=False)
    value_encrypted: Mapped[str] = mapped_column(String, nullable=False)
    commitment: Mapped[str] = mapped_column(String(128), nullable=False)
    salt: Mapped[str] = mapped_column(String(64), nullable=False)

    credential: Mapped["Credential"] = relationship(back_populates="claims")
