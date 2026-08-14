import uuid
from datetime import datetime

from pydantic import BaseModel, Field

from app.models.credential import CredentialStatus, CredentialType


class DIDProfileOut(BaseModel):
    did: str
    public_key_pem: str
    key_algorithm: str
    created_at: datetime

    class Config:
        from_attributes = True


class CredentialOut(BaseModel):
    id: uuid.UUID
    issuer_id: uuid.UUID
    credential_type: CredentialType
    status: CredentialStatus
    schema_version: str
    claims_commitment: str
    issued_at: datetime
    expires_at: datetime | None
    onchain_credential_hash: str | None

    class Config:
        from_attributes = True


class WalletMeOut(BaseModel):
    user_id: uuid.UUID
    email: str
    did: str | None
    credential_count: int
    active_credential_count: int


class GenerateProofRequest(BaseModel):
    credential_id: uuid.UUID
    claim_predicate: str = Field(
        ..., description="e.g. 'age_gte_18', 'is_student_true', 'kyc_valid_true'", max_length=128
    )
    # Optional predicate parameter, e.g. {"threshold": 21} for age_gte_21
    predicate_params: dict = Field(default_factory=dict)


class GenerateProofResponse(BaseModel):
    zk_proof_id: uuid.UUID
    claim_predicate: str
    public_inputs: dict
    proof_blob: str
    expires_at: datetime | None
