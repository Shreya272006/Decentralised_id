import uuid
from datetime import datetime
import enum

from app.db.base import Base, String, Boolean, DateTime, ForeignKey, SAEnum, UUID, JSONB, Mapped, mapped_column, relationship


class AnchorType(str, enum.Enum):
    CREDENTIAL_ISSUANCE = "credential_issuance"
    REVOCATION = "revocation"
    ISSUER_REGISTRATION = "issuer_registration"


class ZKProofRecord(Base):
    """
    Stores a generated zero-knowledge proof and its public inputs/outputs.
    Private witnesses (e.g. exact date of birth) are NEVER persisted here
    or anywhere else — they exist only transiently in the proving process.
    """
    __tablename__ = "zk_proof_records"

    id: Mapped[uuid.UUID] = mapped_column(UUID(as_uuid=True), primary_key=True, default=uuid.uuid4)
    subject_id: Mapped[uuid.UUID] = mapped_column(UUID(as_uuid=True), ForeignKey("users.id", ondelete="CASCADE"), index=True)
    credential_id: Mapped[uuid.UUID] = mapped_column(UUID(as_uuid=True), ForeignKey("credentials.id", ondelete="CASCADE"), index=True)

    claim_predicate: Mapped[str] = mapped_column(String(128), nullable=False)  # e.g. "age_gte_18"
    circuit_id: Mapped[str] = mapped_column(String(64), nullable=False)  # e.g. "range_proof_v1"

    public_inputs: Mapped[dict] = mapped_column(JSONB, nullable=False)  # e.g. {"threshold": 18, "commitment": "0x.."}
    proof_blob: Mapped[str] = mapped_column(String, nullable=False)  # serialized proof (base64)

    is_valid: Mapped[bool] = mapped_column(Boolean, nullable=True)  # set after verification
    verified_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), nullable=True)

    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), default=datetime.utcnow, nullable=False)
    expires_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), nullable=True)


class SmartContractAnchor(Base):
    """Links an off-chain record to its on-chain transaction/state."""
    __tablename__ = "smart_contract_anchors"

    id: Mapped[uuid.UUID] = mapped_column(UUID(as_uuid=True), primary_key=True, default=uuid.uuid4)
    anchor_type: Mapped[str] = mapped_column(SAEnum(AnchorType, name="anchor_type"), nullable=False)
    related_credential_id: Mapped[uuid.UUID] = mapped_column(UUID(as_uuid=True), ForeignKey("credentials.id", ondelete="SET NULL"), nullable=True)

    contract_address: Mapped[str] = mapped_column(String(42), nullable=False)
    tx_hash: Mapped[str] = mapped_column(String(66), nullable=False, unique=True)
    block_number: Mapped[int] = mapped_column(nullable=True)
    onchain_hash: Mapped[str] = mapped_column(String(66), nullable=False)  # bytes32 anchored value

    confirmed: Mapped[bool] = mapped_column(Boolean, default=False, nullable=False)
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), default=datetime.utcnow, nullable=False)
