import uuid
from datetime import datetime
import enum

from app.db.base import Base, String, Boolean, DateTime, ForeignKey, SAEnum, UUID, JSONB, Mapped, mapped_column, relationship, Float, INET


class DocumentStatus(str, enum.Enum):
    PENDING = "pending"
    PROCESSED = "processed"
    FAILED = "failed"


class DocumentUpload(Base):
    """
    Metadata only — the raw document image is encrypted with AES-256-GCM
    and stored in object storage (path referenced here); it is never
    persisted in plaintext or logged.
    """
    __tablename__ = "document_uploads"

    id: Mapped[uuid.UUID] = mapped_column(UUID(as_uuid=True), primary_key=True, default=uuid.uuid4)
    user_id: Mapped[uuid.UUID] = mapped_column(UUID(as_uuid=True), ForeignKey("users.id", ondelete="CASCADE"), index=True)

    document_type: Mapped[str] = mapped_column(String(64), nullable=False)  # passport, national_id, student_id...
    encrypted_storage_path: Mapped[str] = mapped_column(String(512), nullable=False)
    encrypted_storage_iv: Mapped[str] = mapped_column(String(64), nullable=False)
    sha256_fingerprint: Mapped[str] = mapped_column(String(64), nullable=False)  # integrity check, not reversible

    status: Mapped[str] = mapped_column(SAEnum(DocumentStatus, name="document_status"), default=DocumentStatus.PENDING)
    ocr_extracted_fields: Mapped[dict] = mapped_column(JSONB, default=dict, nullable=False)  # non-sensitive/masked only
    tamper_indicators: Mapped[dict] = mapped_column(JSONB, default=dict, nullable=False)

    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), default=datetime.utcnow, nullable=False)


class FaceMatchResult(Base):
    __tablename__ = "face_match_results"

    id: Mapped[uuid.UUID] = mapped_column(UUID(as_uuid=True), primary_key=True, default=uuid.uuid4)
    user_id: Mapped[uuid.UUID] = mapped_column(UUID(as_uuid=True), ForeignKey("users.id", ondelete="CASCADE"), index=True)
    document_upload_id: Mapped[uuid.UUID] = mapped_column(UUID(as_uuid=True), ForeignKey("document_uploads.id", ondelete="SET NULL"), nullable=True)

    similarity_score: Mapped[float] = mapped_column(Float, nullable=False)  # cosine similarity [0,1]
    liveness_passed: Mapped[bool] = mapped_column(default=False, nullable=False)
    liveness_score: Mapped[float] = mapped_column(Float, nullable=True)
    match_passed: Mapped[bool] = mapped_column(default=False, nullable=False)

    # Embeddings are never stored raw — only an encrypted, salted commitment
    # for potential re-verification, never used for cross-service matching.
    embedding_commitment_encrypted: Mapped[str] = mapped_column(String, nullable=True)

    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), default=datetime.utcnow, nullable=False)


class FraudScore(Base):
    __tablename__ = "fraud_scores"

    id: Mapped[uuid.UUID] = mapped_column(UUID(as_uuid=True), primary_key=True, default=uuid.uuid4)
    user_id: Mapped[uuid.UUID] = mapped_column(UUID(as_uuid=True), ForeignKey("users.id", ondelete="CASCADE"), index=True)
    document_upload_id: Mapped[uuid.UUID] = mapped_column(UUID(as_uuid=True), ForeignKey("document_uploads.id", ondelete="SET NULL"), nullable=True)
    face_match_id: Mapped[uuid.UUID] = mapped_column(UUID(as_uuid=True), ForeignKey("face_match_results.id", ondelete="SET NULL"), nullable=True)

    document_score: Mapped[float] = mapped_column(Float, nullable=False)
    face_score: Mapped[float] = mapped_column(Float, nullable=False)
    behavioral_score: Mapped[float] = mapped_column(Float, nullable=False)
    overall_score: Mapped[float] = mapped_column(Float, nullable=False)  # weighted aggregate, higher = riskier

    status: Mapped[str] = mapped_column(String(16), nullable=False)  # APPROVED | REVIEW | REJECTED
    signals: Mapped[dict] = mapped_column(JSONB, default=dict, nullable=False)

    ip_address: Mapped[str] = mapped_column(INET, nullable=True)
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), default=datetime.utcnow, nullable=False)
