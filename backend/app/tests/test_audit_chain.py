import os
import sys
import uuid
from datetime import datetime
from unittest.mock import patch
import pytest

# Ensure backend directory is in the python path
sys.path.insert(0, os.path.abspath(os.path.join(os.path.dirname(__file__), "../..")))

from app.db.session import SessionLocal
from app.models.audit import AuditEvent
from app.services.audit.logger import log_event, verify_chain

def test_audit_chain_identical_timestamps():
    db = SessionLocal()
    db.db["audit_events"].delete_many({})
    
    # Mock datetime.utcnow to return the exact same timestamp
    fixed_time = datetime(2026, 8, 15, 12, 0, 0)
    
    with patch("app.services.audit.logger.datetime") as mock_datetime:
        mock_datetime.utcnow.return_value = fixed_time
        mock_datetime.fromisoformat = datetime.fromisoformat
        
        # Log 5 events with identical timestamps
        for i in range(5):
            log_event(
                db,
                actor_id=str(uuid.uuid4()),
                action=f"test.action.{i}",
                resource_type="test_resource",
                resource_id=f"res_{i}",
                details={"index": i}
            )
            
    db.commit()
    
    try:
        # Query raw documents
        raw_docs = list(db.db["audit_events"].find({}))
        print("\nRaw docs stored in MongoDB:")
        for doc in raw_docs:
            print(f"  ID: {doc.get('id')}, Action: {doc.get('action')}, CreatedAt: {doc.get('created_at')}")
            
        # Verify via the app's verify_chain function
        intact, broken_id = verify_chain(db)
        print(f"App's chain verification result - Intact: {intact}, Broken ID: {broken_id}")
        
        # Reconstruct the chain from prev_hash pointers
        chain = []
        lookup = {doc.get("previous_record_hash"): doc for doc in raw_docs if doc.get("previous_record_hash")}
        
        curr = "GENESIS"
        visited = set()
        while curr in lookup and curr not in visited:
            visited.add(curr)
            doc = lookup[curr]
            chain.append(doc)
            curr = doc.get("record_hash")
            
        print(f"Reconstructed chain length: {len(chain)} / {len(raw_docs)}")
        
        assert intact is True, f"Expected verify_chain to succeed after fixing ordering bug, got intact={intact}, broken_id={broken_id}"
        assert len(chain) == 5, f"Expected 5 chained entries, got {len(chain)}"

        # Now verify that tampering with a record breaks the chain
        # Modify details of event with action test.action.2
        target_id = None
        for doc in raw_docs:
            if doc.get("action") == "test.action.2":
                target_id = doc.get("_id")
                break
                
        assert target_id is not None
        db.db["audit_events"].update_one({"_id": target_id}, {"$set": {"details.tampered": True}})
        
        intact_after_tamper, broken_id_after_tamper = verify_chain(db)
        print(f"Verify chain result after tamper - Intact: {intact_after_tamper}, Broken ID: {broken_id_after_tamper}")
        assert intact_after_tamper is False, "Expected verify_chain to detect tampered event details!"
        # The broken id should be the tampered record or its child
        assert broken_id_after_tamper is not None
    finally:
        db.db["audit_events"].delete_many({})
        db.close()

