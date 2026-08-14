import uuid
from datetime import datetime

from pydantic import BaseModel, Field


class ZKGenerateProofRequest(BaseModel):
    credential_id: uuid.UUID
    claim_predicate: str = Field(..., max_length=128)
    predicate_params: dict = Field(default_factory=dict)


class ZKGenerateProofResponse(BaseModel):
    zk_proof_id: uuid.UUID
    claim_predicate: str
    public_inputs: dict
    proof_blob: str


class ZKVerifyProofRequest(BaseModel):
    zk_proof_id: uuid.UUID


class ZKVerifyProofResponse(BaseModel):
    is_valid: bool
    claim_predicate: str
    verified_at: datetime


class AnchorCredentialRequest(BaseModel):
    credential_id: uuid.UUID


class AnchorRevocationRequest(BaseModel):
    credential_id: uuid.UUID


class AnchorResponse(BaseModel):
    tx_hash: str
    contract_address: str
    onchain_hash: str
    confirmed: bool


class AnchorStatusResponse(BaseModel):
    anchor_type: str
    tx_hash: str
    block_number: int | None
    confirmed: bool
    created_at: datetime
