import uuid
from datetime import datetime

from pydantic import BaseModel, Field

from app.models.consent import ConsentStatus


class ConsentRequestCreate(BaseModel):
    subject_id: uuid.UUID
    requested_scopes: list[str] = Field(..., min_length=1)
    purpose: str = Field(..., min_length=3, max_length=500)
    expires_in_hours: int = Field(default=24, ge=1, le=720)


class ConsentRespondRequest(BaseModel):
    consent_id: uuid.UUID
    approve: bool
    approved_scopes: list[str] | None = Field(
        default=None, description="Subset of requested_scopes the subject actually approves; defaults to all if approving."
    )


class ConsentRevokeRequest(BaseModel):
    consent_id: uuid.UUID


class ConsentOut(BaseModel):
    id: uuid.UUID
    subject_id: uuid.UUID
    verifier_id: uuid.UUID
    requested_scopes: list[str]
    purpose: str
    status: ConsentStatus
    requested_at: datetime
    responded_at: datetime | None
    expires_at: datetime | None

    class Config:
        from_attributes = True
