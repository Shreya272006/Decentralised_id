"""
Import every model module so that `Base.metadata` is fully populated
for Alembic autogeneration and `create_all()` in dev/seed scripts.
"""
from app.models.user import User, IssuerProfile  # noqa: F401
from app.models.did import DIDProfile  # noqa: F401
from app.models.credential import Credential, CredentialClaim, CredentialStatus, CredentialType  # noqa: F401
from app.models.consent import ConsentRecord, ConsentStatus  # noqa: F401
from app.models.audit import AuditEvent, VerificationLog  # noqa: F401
from app.models.ai import DocumentUpload, FaceMatchResult, FraudScore, DocumentStatus  # noqa: F401
from app.models.zk import ZKProofRecord, SmartContractAnchor, AnchorType  # noqa: F401
