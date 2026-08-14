import uuid
from datetime import datetime
import enum

from sqlalchemy import String, DateTime, ForeignKey, Enum as SAEnum
from sqlalchemy.dialects.postgresql import UUID, JSONB, ARRAY
from sqlalchemy.orm import Mapped, mapped_column, relationship

from app.db.base import Base


class ConsentStatus(str, enum.Enum):
    PENDING = "pending"
    APPROVED = "approved"
    DENIED = "denied"
    REVOKED = "revoked"
    EXPIRED = "expired"


class ConsentRecord(Base):
    """
    Tracks a verifier's request to check specific claim scopes against a
    subject's credentials, and the subject's granular approval/denial.
    Nothing is disclosed to the verifier until status == APPROVED.
    """
    __tablename__ = "consent_records"

    id: Mapped[uuid.UUID] = mapped_column(UUID(as_uuid=True), primary_key=True, default=uuid.uuid4)
    subject_id: Mapped[uuid.UUID] = mapped_column(UUID(as_uuid=True), ForeignKey("users.id", ondelete="CASCADE"), index=True)
    verifier_id: Mapped[uuid.UUID] = mapped_column(UUID(as_uuid=True), ForeignKey("users.id", ondelete="CASCADE"), index=True)

    requested_scopes: Mapped[list[str]] = mapped_column(ARRAY(String), nullable=False)  # e.g. ["age_gte_18"]
    purpose: Mapped[str] = mapped_column(String(500), nullable=False)

    status: Mapped[str] = mapped_column(SAEnum(ConsentStatus, name="consent_status"), default=ConsentStatus.PENDING)

    requested_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), default=datetime.utcnow, nullable=False)
    responded_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), nullable=True)
    expires_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), nullable=True)
    revoked_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), nullable=True)

    metadata_json: Mapped[dict] = mapped_column(JSONB, default=dict, nullable=False)

    subject: Mapped["User"] = relationship(foreign_keys=[subject_id], back_populates="consent_records")
    verifier: Mapped["User"] = relationship(foreign_keys=[verifier_id])
