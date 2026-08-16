import os
import sys
import uuid
import pytest
from datetime import datetime

# Ensure backend directory is in the python path
sys.path.insert(0, os.path.abspath(os.path.join(os.path.dirname(__file__), "../..")))

from app.db.session import SessionShim, SessionLocal
from app.models.user import User
from app.models.audit import AuditEvent
from app.services.audit.logger import verify_chain

def test_dirty_tracking_concurrency():
    # Setup test DB connection
    db1 = SessionLocal()
    db2 = SessionLocal()
    
    user_id = uuid.uuid4()
    
    # Initialize user
    user_setup = User(
        id=user_id,
        email="concurrency_test@example.com",
        hashed_password="setup_password",
        is_active=True,
        failed_login_attempts=0
    )
    
    # Ensure a clean state
    db1.delete(user_setup)
    db1.add(user_setup)
    db1.commit()
    
    print("\n--- Concurrency Test Log Start ---")
    
    # Print Initial DB State
    db_check = SessionLocal()
    initial_user = db_check.query(User).filter(User.id == user_id).first()
    print(f"1. Initial User state in DB: {initial_user.to_dict()}")
    db_check.close()
    
    try:
        # 1. Fetch object A in session 1 (no modification)
        user_sess1 = db1.query(User).filter(User.id == user_id).first()
        assert user_sess1 is not None
        assert user_sess1.email == "concurrency_test@example.com"
        print(f"2. Session 1 fetched User A. Stored in session 1 tracked list.")
        
        # 2. Separately update object A via session 2 and commit
        user_sess2 = db2.query(User).filter(User.id == user_id).first()
        assert user_sess2 is not None
        user_sess2.email = "updated_by_session2@example.com"
        db2.add(user_sess2)
        print(f"3. Session 2 updated User A email to '{user_sess2.email}' and added to pending.")
        db2.commit()
        print("4. Session 2 committed.")
        
        # Check DB State after Session 2 Commit
        db_check = SessionLocal()
        after_sess2_user = db_check.query(User).filter(User.id == user_id).first()
        print(f"5. DB state after Session 2 commit: {after_sess2_user.to_dict()}")
        db_check.close()
        
        # 3. Commit session 1 (which fetched the stale object but did NOT modify it)
        print("6. Committing Session 1 (no modification made in Session 1)...")
        db1.commit()
        
        # 4. Fetch the object again and verify that session 2's changes were NOT overwritten by session 1
        db3 = SessionLocal()
        final_user = db3.query(User).filter(User.id == user_id).first()
        print(f"7. DB state after Session 1 commit: {final_user.to_dict()}")
        
        assert final_user.email == "updated_by_session2@example.com", "Session 1's commit overwrote Session 2's updates with stale data!"
        print("--- Concurrency Test Log End ---\n")
        db3.close()
        
    finally:
        db1.delete(user_setup)
        db1.commit()
        db1.close()
        db2.close()


def test_audit_fork_and_orphan_detection():
    db = SessionLocal()
    db.db["audit_events"].delete_many({})
    
    # Create two duplicate audit events with the exact same previous_record_hash
    fixed_prev_hash = "SOME_HASH_123"
    
    event1 = AuditEvent(
        id=uuid.uuid4(),
        actor_id=uuid.uuid4(),
        action="action.fork.1",
        resource_type="test",
        previous_record_hash=fixed_prev_hash,
        record_hash="HASH_FORK_1",
        created_at=datetime.utcnow()
    )
    event2 = AuditEvent(
        id=uuid.uuid4(),
        actor_id=uuid.uuid4(),
        action="action.fork.2",
        resource_type="test",
        previous_record_hash=fixed_prev_hash,
        record_hash="HASH_FORK_2",
        created_at=datetime.utcnow()
    )
    
    # Also add a Genesis record to trigger normal flow
    genesis = AuditEvent(
        id=uuid.uuid4(),
        action="action.genesis",
        resource_type="test",
        previous_record_hash="GENESIS",
        record_hash=fixed_prev_hash,
        created_at=datetime.utcnow()
    )
    
    db.add(genesis)
    db.add(event1)
    db.add(event2)
    db.commit()
    
    try:
        # Call verify_chain and check fork detection
        intact, reason = verify_chain(db)
        print("\n[Fork Test] verify_chain output:", intact, "Reason:", reason)
        assert intact is False
        assert "fork detected" in reason.lower()
        
        # Test orphan detection: remove genesis so event1 and event2 are orphaned
        db.db["audit_events"].delete_many({})
        orphan_event = AuditEvent(
            id=uuid.uuid4(),
            action="action.orphan",
            resource_type="test",
            previous_record_hash="SOME_ORPHAN_PREV",
            record_hash="SOME_ORPHAN_HASH",
            created_at=datetime.utcnow()
        )
        db.add(orphan_event)
        db.commit()
        
        intact_orphan, reason_orphan = verify_chain(db)
        print("[Orphan Test] verify_chain output:", intact_orphan, "Reason:", reason_orphan)
        assert intact_orphan is False
        assert "orphan detected" in reason_orphan.lower()
        
    finally:
        db.db["audit_events"].delete_many({})
        db.commit()
        db.close()
