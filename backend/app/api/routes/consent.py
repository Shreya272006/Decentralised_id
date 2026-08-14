from datetime import datetime

from fastapi import APIRouter, Depends, HTTPException, status
from sqlalchemy.orm import Session

from app.api.deps import Principal, get_current_principal
from app.core.rbac import Role, assert_owner_or_role
from app.db.session import get_db
from app.models.consent import ConsentRecord, ConsentStatus
from app.schemas.consent import (
    ConsentOut,
    ConsentRequestCreate,
    ConsentRespondRequest,
    ConsentRevokeRequest,
)
from app.services.audit.logger import log_event

router = APIRouter(prefix="/consent", tags=["consent"])


@router.post("/request", response_model=ConsentOut, status_code=status.HTTP_201_CREATED)
def request_consent(
    payload: ConsentRequestCreate,
    principal: Principal = Depends(get_current_principal),
    db: Session = Depends(get_db),
):
    """
    Alternate entry point for creating a consent request directly (in
    addition to /verifier/proof-request), restricted to verifiers.
    """
    from app.core.rbac import require_roles  # local import to avoid cycle at module load

    if principal.role != Role.VERIFIER.value:
        raise HTTPException(status_code=status.HTTP_403_FORBIDDEN, detail="Only verifiers can request consent.")

    consent = ConsentRecord(
        subject_id=payload.subject_id,
        verifier_id=principal.user_id,
        requested_scopes=payload.requested_scopes,
        purpose=payload.purpose,
        status=ConsentStatus.PENDING,
    )
    db.add(consent)
    log_event(
        db, actor_id=principal.user_id, action="consent.request_created", resource_type="consent_record",
        details={"subject_id": str(payload.subject_id), "scopes": payload.requested_scopes},
    )
    db.commit()
    db.refresh(consent)
    return consent


@router.post("/respond", response_model=ConsentOut)
def respond_to_consent(
    payload: ConsentRespondRequest,
    principal: Principal = Depends(get_current_principal),
    db: Session = Depends(get_db),
):
    consent = db.query(ConsentRecord).filter(ConsentRecord.id == payload.consent_id).first()
    if consent is None:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Consent request not found.")

    # Only the subject of the consent request may respond to it.
    assert_owner_or_role(principal, str(consent.subject_id))

    if consent.status != ConsentStatus.PENDING:
        raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail="This consent request already has a response.")

    if payload.approve:
        approved = payload.approved_scopes or consent.requested_scopes
        # Granular scoping: never allow approving scopes beyond what was
        # actually requested.
        invalid_scopes = set(approved) - set(consent.requested_scopes)
        if invalid_scopes:
            raise HTTPException(
                status_code=status.HTTP_400_BAD_REQUEST,
                detail=f"Cannot approve scopes that were not requested: {sorted(invalid_scopes)}",
            )
        consent.requested_scopes = approved
        consent.status = ConsentStatus.APPROVED
    else:
        consent.status = ConsentStatus.DENIED

    consent.responded_at = datetime.utcnow()

    log_event(
        db, actor_id=principal.user_id, action="consent.responded", resource_type="consent_record",
        resource_id=str(consent.id), details={"approved": payload.approve, "scopes": consent.requested_scopes},
    )
    db.commit()
    db.refresh(consent)
    return consent


@router.post("/revoke", response_model=ConsentOut)
def revoke_consent(
    payload: ConsentRevokeRequest,
    principal: Principal = Depends(get_current_principal),
    db: Session = Depends(get_db),
):
    consent = db.query(ConsentRecord).filter(ConsentRecord.id == payload.consent_id).first()
    if consent is None:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Consent request not found.")

    # Only the subject may revoke previously granted consent.
    assert_owner_or_role(principal, str(consent.subject_id))

    if consent.status != ConsentStatus.APPROVED:
        raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail="Only approved consent can be revoked.")

    consent.status = ConsentStatus.REVOKED
    consent.revoked_at = datetime.utcnow()

    log_event(
        db, actor_id=principal.user_id, action="consent.revoked", resource_type="consent_record",
        resource_id=str(consent.id),
    )
    db.commit()
    db.refresh(consent)
    return consent


@router.get("/history", response_model=list[ConsentOut])
def consent_history(
    principal: Principal = Depends(get_current_principal),
    db: Session = Depends(get_db),
):
    # Users see consent records where they are the subject; verifiers see
    # ones where they are the requester — each scoped to their own id.
    if principal.role == Role.VERIFIER.value:
        return db.query(ConsentRecord).filter(ConsentRecord.verifier_id == principal.user_id).all()
    return db.query(ConsentRecord).filter(ConsentRecord.subject_id == principal.user_id).all()
