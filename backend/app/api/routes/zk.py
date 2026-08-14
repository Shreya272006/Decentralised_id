import uuid
from datetime import datetime, timedelta

from fastapi import APIRouter, Depends, HTTPException, Request, status
from sqlalchemy.orm import Session

from app.api.deps import Principal, get_current_principal
from app.core.config import settings
from app.core.rate_limit import limiter
from app.core.security import decrypt_field
from app.db.session import get_db
from app.models.credential import Credential, CredentialClaim, CredentialStatus
from app.models.zk import ZKProofRecord
from app.schemas.zk import (
    ZKGenerateProofRequest,
    ZKGenerateProofResponse,
    ZKVerifyProofRequest,
    ZKVerifyProofResponse,
)
from app.services.audit.logger import log_event
from app.services.zk.proof_engine import generate_proof, verify_proof

router = APIRouter(prefix="/zk", tags=["zk"])


@router.post("/generate-proof", response_model=ZKGenerateProofResponse)
@limiter.limit(settings.RATE_LIMIT_VERIFY)
def zk_generate_proof(
    request: Request,
    payload: ZKGenerateProofRequest,
    principal: Principal = Depends(get_current_principal),
    db: Session = Depends(get_db),
):
    credential = (
        db.query(Credential)
        .filter(Credential.id == payload.credential_id, Credential.holder_id == principal.user_id)
        .first()
    )
    if credential is None:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Credential not found.")
    if credential.status != CredentialStatus.ACTIVE:
        raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail=f"Credential is {credential.status}.")

    claim_key = payload.claim_predicate.split("_gte_")[0].split("_eq_")[0]
    claim = (
        db.query(CredentialClaim)
        .filter(CredentialClaim.credential_id == credential.id, CredentialClaim.claim_key == claim_key)
        .first()
    )
    if claim is None:
        raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail=f"No claim '{claim_key}' on this credential.")

    try:
        proof = generate_proof(
            claim_value=decrypt_field(claim.value_encrypted),
            salt=claim.salt,
            credential_commitment=claim.commitment,
            predicate=payload.claim_predicate,
        )
    except ValueError as exc:
        raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail=str(exc))

    record = ZKProofRecord(
        id=uuid.uuid4(),
        subject_id=principal.user_id,
        credential_id=credential.id,
        claim_predicate=payload.claim_predicate,
        circuit_id="pedersen_or_proof_v1",
        public_inputs=proof.public_inputs,
        proof_blob=proof.proof_blob,
        expires_at=datetime.utcnow() + timedelta(hours=1),
    )
    db.add(record)
    log_event(
        db, actor_id=principal.user_id, action="zk.proof_generated", resource_type="zk_proof_record",
        resource_id=str(record.id), details={"predicate": payload.claim_predicate},
    )
    db.commit()
    db.refresh(record)

    return ZKGenerateProofResponse(
        zk_proof_id=record.id,
        claim_predicate=record.claim_predicate,
        public_inputs=record.public_inputs,
        proof_blob=record.proof_blob,
    )


@router.post("/verify-proof", response_model=ZKVerifyProofResponse)
@limiter.limit(settings.RATE_LIMIT_VERIFY)
def zk_verify_proof(
    request: Request,
    payload: ZKVerifyProofRequest,
    principal: Principal = Depends(get_current_principal),
    db: Session = Depends(get_db),
):
    record = db.query(ZKProofRecord).filter(ZKProofRecord.id == payload.zk_proof_id).first()
    if record is None:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Proof record not found.")

    is_valid = verify_proof(public_inputs=record.public_inputs, proof_blob=record.proof_blob)
    record.is_valid = is_valid
    record.verified_at = datetime.utcnow()

    log_event(
        db, actor_id=principal.user_id, action="zk.proof_verified", resource_type="zk_proof_record",
        resource_id=str(record.id), details={"is_valid": is_valid},
    )
    db.commit()

    return ZKVerifyProofResponse(is_valid=is_valid, claim_predicate=record.claim_predicate, verified_at=record.verified_at)
