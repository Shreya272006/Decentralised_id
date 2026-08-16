import os
import sys
import uuid
import pytest
from fastapi.testclient import TestClient

# Ensure backend directory is in the python path
sys.path.insert(0, os.path.abspath(os.path.join(os.path.dirname(__file__), "../..")))

from app.main import app
from app.db.session import SessionLocal
from app.models.user import User
from app.models.credential import Credential

client = TestClient(app)

def test_e2e_and_idor_flow():
    # -------------------------------------------------------------
    # 0. Setup and fetch seeded users
    # -------------------------------------------------------------
    db = SessionLocal()
    alice_user = db.query(User).filter(User.email == "alice@example.com").first()
    bob_user = db.query(User).filter(User.email == "bob@example.com").first()
    verifier_user = db.query(User).filter(User.email == "verifier@bar-nightclub.com").first()
    admin_user = db.query(User).filter(User.email == "admin@decentraid.dev").first()
    
    assert alice_user is not None
    assert bob_user is not None
    assert verifier_user is not None
    assert admin_user is not None
    
    alice_cred = db.query(Credential).filter(Credential.holder_id == alice_user.id).first()
    bob_cred = db.query(Credential).filter(Credential.holder_id == bob_user.id).first()
    
    assert alice_cred is not None
    assert bob_cred is not None
    db.close()

    # -------------------------------------------------------------
    # 1. Login as Alice
    # -------------------------------------------------------------
    print("\n[Step 1] Logging in as Alice...")
    login_resp = client.post("/api/auth/login", json={
        "email": "alice@example.com",
        "password": "AlicePass!2024"
    })
    assert login_resp.status_code == 200
    alice_cookies = dict(login_resp.cookies)
    print("Alice login response:", login_resp.json())

    # Generate ZK proof for age_gte_18
    print("[Step 1.1] Generating ZK proof for Alice (age_gte_18)...")
    csrf_headers_alice = {"X-CSRF-Token": alice_cookies.get("csrf_token") or ""}
    proof_resp = client.post("/api/wallet/generate-proof", headers=csrf_headers_alice, cookies=alice_cookies, json={
        "credential_id": str(alice_cred.id),
        "claim_predicate": "age_gte_18"
    })
    print("Alice generate proof response:", proof_resp.json())
    assert proof_resp.status_code == 200
    proof_data = proof_resp.json()
    assert "zk_proof_id" in proof_data
    alice_proof_id = proof_data["zk_proof_id"]
    
    # Assert proof does NOT contain raw DOB or age anywhere in the response
    raw_response_str = proof_resp.text
    assert "2001-03-14" not in raw_response_str
    assert '"23"' not in raw_response_str
    assert "age_gte_18" in raw_response_str

    # -------------------------------------------------------------
    # 2. Login as Verifier
    # -------------------------------------------------------------
    print("\n[Step 2] Logging in as Verifier...")
    login_resp = client.post("/api/auth/login", json={
        "email": "verifier@bar-nightclub.com",
        "password": "VerifierPass!2024"
    })
    assert login_resp.status_code == 200
    verifier_cookies = dict(login_resp.cookies)
    print("Verifier login response:", login_resp.json())

    # Send proof request to Alice for scope age_gte_18
    print("[Step 2.1] Creating proof request for Alice...")
    csrf_headers_verifier = {"X-CSRF-Token": verifier_cookies.get("csrf_token") or ""}
    request_resp = client.post("/api/verifier/proof-request", headers=csrf_headers_verifier, cookies=verifier_cookies, json={
        "subject_email": "alice@example.com",
        "requested_scopes": ["age_gte_18"],
        "purpose": "Age verification for venue entry",
        "expires_in_hours": 1
    })
    print("Verifier proof request response:", request_resp.json())
    assert request_resp.status_code == 201
    consent_id = request_resp.json()["consent_id"]

    # -------------------------------------------------------------
    # 3. Login as Alice & approve consent
    # -------------------------------------------------------------
    print("\n[Step 3] Alice approving pending consent request...")
    respond_resp = client.post("/api/consent/respond", headers=csrf_headers_alice, cookies=alice_cookies, json={
        "consent_id": consent_id,
        "approve": True
    })
    print("Alice consent approval response:", respond_resp.json())
    assert respond_resp.status_code == 200
    assert respond_resp.json()["status"] == "approved"

    # -------------------------------------------------------------
    # 4. Login as Verifier & submit consent_id + proof_id
    # -------------------------------------------------------------
    print("\n[Step 4] Verifying Alice's submitted proof...")
    verify_resp = client.post("/api/verifier/verify-proof", headers=csrf_headers_verifier, cookies=verifier_cookies, json={
        "consent_id": consent_id,
        "zk_proof_id": alice_proof_id
    })
    print("Verifier verify-proof response:", verify_resp.json())
    assert verify_resp.status_code == 200
    assert verify_resp.json()["result"] == "valid"

    # -------------------------------------------------------------
    # 5. Login as Admin & check integrity
    # -------------------------------------------------------------
    print("\n[Step 5] Logging in as Admin & checking integrity...")
    login_resp = client.post("/api/auth/login", json={
        "email": "admin@decentraid.dev",
        "password": "AdminPass!2024"
    })
    assert login_resp.status_code == 200
    admin_cookies = dict(login_resp.cookies)
    
    integrity_resp = client.get("/api/admin/logs/integrity", cookies=admin_cookies)
    print("Admin integrity check response:", integrity_resp.json())
    assert integrity_resp.status_code == 200
    assert integrity_resp.json() == {"intact": True, "first_broken_record_id": None}

    # -------------------------------------------------------------
    # 6. Negative Case: Bob (under-18) ZK proof generation for age_gte_18
    # -------------------------------------------------------------
    print("\n[Negative Case] Logging in as Bob...")
    login_resp = client.post("/api/auth/login", json={
        "email": "bob@example.com",
        "password": "BobPass!2024"
    })
    assert login_resp.status_code == 200
    bob_cookies = dict(login_resp.cookies)
    
    # Try generating proof for age_gte_18
    print("Bob generating proof for age_gte_18...")
    csrf_headers_bob = {"X-CSRF-Token": bob_cookies.get("csrf_token") or ""}
    bob_proof_resp = client.post("/api/wallet/generate-proof", headers=csrf_headers_bob, cookies=bob_cookies, json={
        "credential_id": str(bob_cred.id),
        "claim_predicate": "age_gte_18"
    })
    print("Bob generate proof response:", bob_proof_resp.json())
    # Should either fail proof generation (400) or produce a proof that verifies as invalid.
    # Let's handle both possible valid ways:
    if bob_proof_resp.status_code == 200:
        # If it returns a proof, it must fail verification
        bob_proof_id = bob_proof_resp.json()["zk_proof_id"]
        # Create consent request for Bob
        req_resp = client.post("/api/verifier/proof-request", headers=csrf_headers_verifier, cookies=verifier_cookies, json={
            "subject_email": "bob@example.com",
            "requested_scopes": ["age_gte_18"],
            "purpose": "Check Bob age",
            "expires_in_hours": 1
        })
        bob_consent_id = req_resp.json()["consent_id"]
        # Approve
        client.post("/api/consent/respond", headers=csrf_headers_bob, cookies=bob_cookies, json={
            "consent_id": bob_consent_id,
            "approve": True
        })
        # Verify
        v_resp = client.post("/api/verifier/verify-proof", headers=csrf_headers_verifier, cookies=verifier_cookies, json={
            "consent_id": bob_consent_id,
            "zk_proof_id": bob_proof_id
        })
        print("Bob verify response:", v_resp.json())
        assert v_resp.json()["result"] != "valid"
    else:
        assert bob_proof_resp.status_code == 400
        assert "witness" in bob_proof_resp.json()["detail"].lower() or "satisfy" in bob_proof_resp.json()["detail"].lower() or "failed" in bob_proof_resp.json()["detail"].lower()
        
    # Check that Bob's actual DOB or age ("2008-07-01", "16") is not leaked
    assert "2008-07-01" not in bob_proof_resp.text
    assert '"16"' not in bob_proof_resp.text

    # -------------------------------------------------------------
    # 7. IDOR / ownership boundary tests
    # -------------------------------------------------------------
    print("\n[IDOR Tests] Testing cross-account access boundaries...")
    # Bob attempts to respond to Alice's consent request
    bob_respond = client.post("/api/consent/respond", headers=csrf_headers_bob, cookies=bob_cookies, json={
        "consent_id": consent_id,
        "approve": True
    })
    print("Bob responding to Alice's consent status:", bob_respond.status_code, bob_respond.json())
    assert bob_respond.status_code == 403
    assert "access" in bob_respond.json()["detail"].lower()
    
    # Alice attempts to generate a proof using Bob's credential
    alice_generate_bob_cred = client.post("/api/wallet/generate-proof", headers=csrf_headers_alice, cookies=alice_cookies, json={
        "credential_id": str(bob_cred.id),
        "claim_predicate": "age_gte_18"
    })
    print("Alice generating proof for Bob's credential status:", alice_generate_bob_cred.status_code, alice_generate_bob_cred.json())
    assert alice_generate_bob_cred.status_code == 404
    
    # Alice attempts to access verifier endpoints (which require Role.VERIFIER)
    alice_verifier_access = client.get("/api/verifier/history", cookies=alice_cookies)
    print("Alice calling verifier history status:", alice_verifier_access.status_code, alice_verifier_access.json())
    assert alice_verifier_access.status_code == 403
