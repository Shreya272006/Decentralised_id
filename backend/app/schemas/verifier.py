import uuid
from datetime import datetime

from pydantic import BaseModel, EmailStr, Field


class ProofRequestCreate(BaseModel):
    subject_email: EmailStr
    requested_scopes: list[str] = Field(..., min_length=1, description="e.g. ['age_gte_18']")
    purpose: str = Field(..., min_length=3, max_length=500)
    expires_in_hours: int = Field(default=24, ge=1, le=720)


class ProofRequestOut(BaseModel):
    consent_id: uuid.UUID
    subject_id: uuid.UUID
    requested_scopes: list[str]
    status: str
    requested_at: datetime
    expires_at: datetime | None


class VerifyProofRequest(BaseModel):
    consent_id: uuid.UUID
    zk_proof_id: uuid.UUID


class VerifyProofResponse(BaseModel):
    result: str  # "valid" | "invalid" | "revoked" | "expired" | "consent_denied"
    claim_predicate: str
    verified_at: datetime
    credential_status: str | None


class VerificationHistoryItem(BaseModel):
    id: uuid.UUID
    subject_id: uuid.UUID | None
    claim_scope: str
    result: str
    created_at: datetime

    class Config:
        from_attributes = True
