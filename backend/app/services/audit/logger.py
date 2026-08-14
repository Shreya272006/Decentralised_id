"""
Tamper-evident audit trail. Every security-relevant action is written
as a hash-chained `AuditEvent`: each record embeds the sha256 of the
previous record plus its own canonical fields, so any retroactive edit
or deletion breaks the chain and can be detected by `verify_chain`.
"""
import json
import uuid
from datetime import datetime
from typing import Optional

from sqlalchemy.orm import Session

from app.core.security import sha256_hex
from app.models.audit import AuditEvent


def _canonical(event_fields: dict) -> bytes:
    return json.dumps(event_fields, sort_keys=True, default=str).encode("utf-8")


def log_event(
    db: Session,
    *,
    actor_id: Optional[str],
    action: str,
    resource_type: str,
    resource_id: Optional[str] = None,
    ip_address: Optional[str] = None,
    user_agent: Optional[str] = None,
    device_fingerprint: Optional[str] = None,
    details: Optional[dict] = None,
) -> AuditEvent:
    last = db.query(AuditEvent).order_by(AuditEvent.created_at.desc()).first()
    previous_hash = last.record_hash if last else "GENESIS"
    timestamp = datetime.utcnow()

    fields = {
        "actor_id": str(actor_id) if actor_id else None,
        "action": action,
        "resource_type": resource_type,
        "resource_id": resource_id,
        "details": details or {},
        "previous_record_hash": previous_hash,
        "timestamp": timestamp.isoformat(),
    }
    record_hash = sha256_hex(_canonical(fields))

    event = AuditEvent(
        id=uuid.uuid4(),
        actor_id=actor_id,
        action=action,
        resource_type=resource_type,
        resource_id=resource_id,
        ip_address=ip_address,
        user_agent=user_agent,
        device_fingerprint=device_fingerprint,
        details=details or {},
        previous_record_hash=previous_hash,
        record_hash=record_hash,
        created_at=timestamp,
    )
    db.add(event)
    db.flush()
    return event


def verify_chain(db: Session) -> tuple[bool, Optional[str]]:
    """
    Replays the entire audit chain in insertion order and confirms each
    record's stored hash matches a recomputed hash from its fields and
    the previous record's hash. Returns (is_intact, first_broken_id).
    """
    events = db.query(AuditEvent).order_by(AuditEvent.created_at.asc()).all()
    previous_hash = "GENESIS"
    for event in events:
        fields = {
            "actor_id": str(event.actor_id) if event.actor_id else None,
            "action": event.action,
            "resource_type": event.resource_type,
            "resource_id": event.resource_id,
            "details": event.details or {},
            "previous_record_hash": previous_hash,
            "timestamp": event.created_at.isoformat(),
        }
        expected_hash = sha256_hex(_canonical(fields))
        if expected_hash != event.record_hash or event.previous_record_hash != previous_hash:
            return False, str(event.id)
        previous_hash = event.record_hash
    return True, None
