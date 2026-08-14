import uuid
from datetime import datetime

from pydantic import BaseModel


class AdminUserOut(BaseModel):
    id: uuid.UUID
    email: str
    role: str
    is_active: bool
    is_blocked: bool
    created_at: datetime

    class Config:
        from_attributes = True


class AdminIssuerOut(BaseModel):
    id: uuid.UUID
    user_id: uuid.UUID
    organization_name: str
    is_approved: bool
    is_blocked: bool
    created_at: datetime

    class Config:
        from_attributes = True


class AdminAuditLogOut(BaseModel):
    id: uuid.UUID
    actor_id: uuid.UUID | None
    action: str
    resource_type: str
    resource_id: str | None
    created_at: datetime

    class Config:
        from_attributes = True


class ApproveIssuerRequest(BaseModel):
    issuer_profile_id: uuid.UUID


class BlockIssuerRequest(BaseModel):
    issuer_profile_id: uuid.UUID
    reason: str
