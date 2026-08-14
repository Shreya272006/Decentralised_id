import uuid

from fastapi import APIRouter, Depends, HTTPException, status
from sqlalchemy.orm import Session

from app.api.deps import Principal, get_current_principal
from app.core.rbac import Role, require_roles
from app.db.session import get_db
from app.models.credential import Credential, CredentialStatus
from app.models.zk import AnchorType, SmartContractAnchor
from app.schemas.zk import (
    AnchorCredentialRequest,
    AnchorResponse,
    AnchorRevocationRequest,
    AnchorStatusResponse,
)
from app.services.audit.logger import log_event
from app.services.blockchain.connector import blockchain_connector
from app.core.config import settings

router = APIRouter(prefix="/blockchain", tags=["blockchain"])


@router.post("/anchor-credential", response_model=AnchorResponse)
def anchor_credential(
    payload: AnchorCredentialRequest,
    principal: Principal = Depends(require_roles(Role.ISSUER, Role.ADMIN)),
    db: Session = Depends(get_db),
):
    credential = db.query(Credential).filter(Credential.id == payload.credential_id).first()
    if credential is None:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Credential not found.")
    if str(credential.issuer_id) != principal.user_id and principal.role != Role.ADMIN.value:
        raise HTTPException(status_code=status.HTTP_403_FORBIDDEN, detail="Only the issuing organization can anchor this credential.")

    try:
        result = blockchain_connector.anchor_credential(str(credential.id), credential.claims_commitment)
    except RuntimeError as exc:
        raise HTTPException(status_code=status.HTTP_503_SERVICE_UNAVAILABLE, detail=str(exc))

    credential.blockchain_tx_hash = result.tx_hash
    credential.onchain_credential_hash = f"0x{credential.claims_commitment[:64]}"

    anchor = SmartContractAnchor(
        id=uuid.uuid4(),
        anchor_type=AnchorType.CREDENTIAL_ISSUANCE,
        related_credential_id=credential.id,
        contract_address=settings.CREDENTIAL_REGISTRY_ADDRESS,
        tx_hash=result.tx_hash,
        block_number=result.block_number,
        onchain_hash=credential.onchain_credential_hash,
        confirmed=result.confirmed,
    )
    db.add(anchor)

    log_event(
        db, actor_id=principal.user_id, action="blockchain.anchor_credential", resource_type="credential",
        resource_id=str(credential.id), details={"tx_hash": result.tx_hash},
    )
    db.commit()

    return AnchorResponse(
        tx_hash=result.tx_hash,
        contract_address=anchor.contract_address,
        onchain_hash=anchor.onchain_hash,
        confirmed=result.confirmed,
    )


@router.post("/anchor-revocation", response_model=AnchorResponse)
def anchor_revocation(
    payload: AnchorRevocationRequest,
    principal: Principal = Depends(require_roles(Role.ISSUER, Role.ADMIN)),
    db: Session = Depends(get_db),
):
    credential = db.query(Credential).filter(Credential.id == payload.credential_id).first()
    if credential is None:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Credential not found.")
    if credential.status != CredentialStatus.REVOKED:
        raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail="Credential must be revoked before anchoring revocation.")
    if str(credential.issuer_id) != principal.user_id and principal.role != Role.ADMIN.value:
        raise HTTPException(status_code=status.HTTP_403_FORBIDDEN, detail="Only the issuing organization can anchor this revocation.")

    try:
        result = blockchain_connector.anchor_revocation(str(credential.id), credential.claims_commitment)
    except RuntimeError as exc:
        raise HTTPException(status_code=status.HTTP_503_SERVICE_UNAVAILABLE, detail=str(exc))

    anchor = SmartContractAnchor(
        id=uuid.uuid4(),
        anchor_type=AnchorType.REVOCATION,
        related_credential_id=credential.id,
        contract_address=settings.REVOCATION_REGISTRY_ADDRESS,
        tx_hash=result.tx_hash,
        block_number=result.block_number,
        onchain_hash=f"0x{credential.claims_commitment[:64]}",
        confirmed=result.confirmed,
    )
    db.add(anchor)

    log_event(
        db, actor_id=principal.user_id, action="blockchain.anchor_revocation", resource_type="credential",
        resource_id=str(credential.id), details={"tx_hash": result.tx_hash},
    )
    db.commit()

    return AnchorResponse(
        tx_hash=result.tx_hash, contract_address=anchor.contract_address, onchain_hash=anchor.onchain_hash, confirmed=result.confirmed
    )


@router.get("/status/{anchor_id}", response_model=AnchorStatusResponse)
def anchor_status(
    anchor_id: uuid.UUID,
    principal: Principal = Depends(get_current_principal),
    db: Session = Depends(get_db),
):
    anchor = db.query(SmartContractAnchor).filter(SmartContractAnchor.id == anchor_id).first()
    if anchor is None:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Anchor record not found.")

    return AnchorStatusResponse(
        anchor_type=anchor.anchor_type,
        tx_hash=anchor.tx_hash,
        block_number=anchor.block_number,
        confirmed=anchor.confirmed,
        created_at=anchor.created_at,
    )
