import uuid
from datetime import datetime

from app.db.base import Base, String, Boolean, DateTime, ForeignKey, SAEnum, UUID, JSONB, Mapped, mapped_column, relationship


class DIDProfile(Base):
    """
    Maps a platform user to a W3C-style Decentralized Identifier and the
    public key material used to verify signatures over their credentials.
    Private keys never touch the server — only public keys are stored.
    """
    __tablename__ = "did_profiles"

    id: Mapped[uuid.UUID] = mapped_column(UUID(as_uuid=True), primary_key=True, default=uuid.uuid4)
    user_id: Mapped[uuid.UUID] = mapped_column(UUID(as_uuid=True), ForeignKey("users.id", ondelete="CASCADE"), unique=True)

    did: Mapped[str] = mapped_column(String(255), unique=True, nullable=False, index=True)  # e.g. did:key:z6Mk...
    public_key_pem: Mapped[str] = mapped_column(String(2048), nullable=False)
    key_algorithm: Mapped[str] = mapped_column(String(32), default="Ed25519", nullable=False)

    did_document: Mapped[dict] = mapped_column(JSONB, default=dict, nullable=False)

    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), default=datetime.utcnow, nullable=False)
    rotated_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), nullable=True)

    user: Mapped["User"] = relationship(back_populates="did_profile")
