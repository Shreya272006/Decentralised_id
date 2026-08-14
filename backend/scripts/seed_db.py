"""
Seeds the database with demo users, an approved issuer, sample
credentials, and a verification log entry — so the platform is
immediately explorable after `docker-compose up --build`.

Run with:  python -m scripts.seed_db
"""
import hashlib
import secrets
import sys
import uuid
from datetime import datetime, timedelta

sys.path.insert(0, ".")

from app.db.init_db import init_db
from app.db.session import SessionLocal
from app.core.security import encrypt_field, hash_password
from app.core.rbac import Role
from app.models.user import User, IssuerProfile
from app.models.did import DIDProfile
from app.models.credential import Credential, CredentialClaim, CredentialStatus, CredentialType
from app.models.consent import ConsentRecord, ConsentStatus
from app.models.audit import VerificationLog
from cryptography.hazmat.primitives.asymmetric.ed25519 import Ed25519PrivateKey
from cryptography.hazmat.primitives import serialization


def make_did_profile(db, user_id):
    private_key = Ed25519PrivateKey.generate()
    public_pem = private_key.public_key().public_bytes(
        encoding=serialization.Encoding.PEM, format=serialization.PublicFormat.SubjectPublicKeyInfo
    ).decode()
    did_value = f"did:key:z{uuid.uuid4().hex}"
    profile = DIDProfile(
        id=uuid.uuid4(), user_id=user_id, did=did_value, public_key_pem=public_pem,
        key_algorithm="Ed25519", did_document={"id": did_value},
    )
    db.add(profile)
    return profile


def make_user(db, email, password, role, full_name):
    user = User(
        id=uuid.uuid4(), email=email, hashed_password=hash_password(password),
        full_name_encrypted=encrypt_field(full_name), role=role, is_active=True, is_verified=True,
    )
    db.add(user)
    db.flush()
    make_did_profile(db, user.id)
    return user


def issue_demo_credential(db, holder, issuer, credential_type, claims, days_valid=365):
    signing_key_id = f"issuer:{issuer.id}"
    claim_commitments, claim_rows = [], []
    for key in sorted(claims.keys()):
        value = claims[key]
        salt = secrets.token_hex(16)
        commitment = hashlib.sha256(f"{salt}{value}".encode()).hexdigest()
        claim_commitments.append(f"{key}:{commitment}")
        claim_rows.append((key, value, salt, commitment))

    overall_commitment = hashlib.sha256("|".join(claim_commitments).encode()).hexdigest()
    signature = hashlib.sha256(f"{signing_key_id}{overall_commitment}".encode()).hexdigest()

    credential = Credential(
        id=uuid.uuid4(), holder_id=holder.id, issuer_id=issuer.id, credential_type=credential_type,
        status=CredentialStatus.ACTIVE, claims_encrypted=encrypt_field(str(sorted(claims.items()))),
        claims_commitment=overall_commitment, issuer_signature=signature, signing_key_id=signing_key_id,
        issued_at=datetime.utcnow(), expires_at=datetime.utcnow() + timedelta(days=days_valid),
    )
    db.add(credential)
    db.flush()

    for key, value, salt, commitment in claim_rows:
        db.add(CredentialClaim(
            id=uuid.uuid4(), credential_id=credential.id, claim_key=key,
            value_encrypted=encrypt_field(value), commitment=commitment, salt=salt,
        ))
    return credential


def run():
    init_db()
    db = SessionLocal()
    try:
        if db.query(User).filter(User.email == "admin@decentraid.dev").first():
            print("Seed data already present — skipping.")
            return

        admin = make_user(db, "admin@decentraid.dev", "AdminPass!2024", Role.ADMIN, "Platform Admin")

        issuer_user = make_user(db, "issuer@university.edu", "IssuerPass!2024", Role.ISSUER, "State University Registrar")
        issuer_profile = IssuerProfile(
            id=uuid.uuid4(), user_id=issuer_user.id, organization_name="State University",
            organization_domain="university.edu", is_approved=True,
        )
        db.add(issuer_profile)

        verifier_user = make_user(db, "verifier@bar-nightclub.com", "VerifierPass!2024", Role.VERIFIER, "Downtown Nightclub")

        alice = make_user(db, "alice@example.com", "AlicePass!2024", Role.USER, "Alice Johnson")
        bob = make_user(db, "bob@example.com", "BobPass!2024", Role.USER, "Bob Martinez")

        db.flush()

        cred1 = issue_demo_credential(
            db, alice, issuer_user, CredentialType.AGE_VERIFICATION,
            {"date_of_birth": "2001-03-14", "age": "23"},
        )
        cred2 = issue_demo_credential(
            db, alice, issuer_user, CredentialType.STUDENT_STATUS,
            {"enrollment_status": "active", "is_student": "true"},
        )
        cred3 = issue_demo_credential(
            db, bob, issuer_user, CredentialType.AGE_VERIFICATION,
            {"date_of_birth": "2008-07-01", "age": "16"},
        )

        consent = ConsentRecord(
            id=uuid.uuid4(), subject_id=alice.id, verifier_id=verifier_user.id,
            requested_scopes=["age_gte_18"], purpose="Age verification for venue entry",
            status=ConsentStatus.APPROVED, responded_at=datetime.utcnow(),
            expires_at=datetime.utcnow() + timedelta(hours=24),
        )
        db.add(consent)

        db.add(VerificationLog(
            id=uuid.uuid4(), verifier_id=verifier_user.id, subject_id=alice.id,
            credential_id=cred1.id, consent_id=consent.id, claim_scope="age_gte_18", result="valid",
        ))

        db.commit()
        print("Seed complete:")
        print("  Admin:    admin@decentraid.dev / AdminPass!2024")
        print("  Issuer:   issuer@university.edu / IssuerPass!2024")
        print("  Verifier: verifier@bar-nightclub.com / VerifierPass!2024")
        print("  User:     alice@example.com / AlicePass!2024 (has age_verification + student_status credentials)")
        print("  User:     bob@example.com / BobPass!2024 (has an under-18 age_verification credential)")
    finally:
        db.close()


if __name__ == "__main__":
    run()
