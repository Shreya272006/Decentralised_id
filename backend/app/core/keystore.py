import os
from cryptography.hazmat.primitives.asymmetric import ed25519
from cryptography.hazmat.primitives import serialization

KEYS_DIR = os.path.abspath(os.path.join(os.path.dirname(__file__), "../../../keys"))

def get_issuer_signing_key(issuer_id: str) -> ed25519.Ed25519PrivateKey:
    """
    Retrieves the private Ed25519 signing key for the specified issuer.
    In a real production environment, this would call a KMS/HSM service.
    For local development, we load/save PEM files under a 'keys' directory.
    """
    os.makedirs(KEYS_DIR, exist_ok=True)
    key_path = os.path.join(KEYS_DIR, f"issuer_{issuer_id}_private.pem")
    
    if os.path.exists(key_path):
        with open(key_path, "rb") as f:
            return serialization.load_pem_private_key(f.read(), password=None)
            
    # If key doesn't exist, generate one for local dev
    private_key = ed25519.Ed25519PrivateKey.generate()
    private_bytes = private_key.private_bytes(
        encoding=serialization.Encoding.PEM,
        format=serialization.PrivateFormat.PKCS8,
        encryption_algorithm=serialization.NoEncryption()
    )
    with open(key_path, "wb") as f:
        f.write(private_bytes)
        
    return private_key

def get_issuer_verification_key(issuer_id: str) -> ed25519.Ed25519PublicKey:
    """
    Retrieves the public Ed25519 verification key for the specified issuer.
    """
    private_key = get_issuer_signing_key(issuer_id)
    return private_key.public_key()

def is_issuer_key_active(issuer_id: str, db) -> bool:
    """
    Checks if the issuer's key status is active.
    An issuer key is active if their profile exists in the DB, is approved,
    and is not blocked.
    """
    from app.models.user import IssuerProfile
    profile = db.query(IssuerProfile).filter(IssuerProfile.user_id == issuer_id).first()
    if profile is None:
        return False
    return profile.is_approved and not profile.is_blocked
