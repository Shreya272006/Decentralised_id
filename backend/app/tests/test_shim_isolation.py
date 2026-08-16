import os
import sys
import uuid
from datetime import datetime, timedelta
import pytest

# Ensure backend directory is in the python path
sys.path.insert(0, os.path.abspath(os.path.join(os.path.dirname(__file__), "../..")))

from app.db.base import Base
from app.db.session import SessionLocal, get_db
from app.models.user import User

def test_shim_operators_and_queries():
    db = SessionLocal()
    
    # 1. Setup test data
    user_id_1 = uuid.uuid4()
    user_id_2 = uuid.uuid4()
    
    now = datetime.utcnow().replace(microsecond=0)
    past = now - timedelta(days=5)
    future = now + timedelta(days=5)
    
    user1 = User(
        id=user_id_1,
        email="test_user1@example.com",
        hashed_password="pw1",
        created_at=past,
        metadata_json={"role_info": {"level": 2}, "tags": ["test", "user1"]}
    )
    user2 = User(
        id=user_id_2,
        email="test_user2@example.com",
        hashed_password="pw2",
        created_at=future,
        metadata_json={"role_info": {"level": 5}, "tags": ["test", "user2"]}
    )
    
    # Clean up any existing test records first
    db.delete(user1)
    db.delete(user2)
    
    db.add(user1)
    db.add(user2)
    db.commit()
    
    try:
        # Test Operator: == against UUID and String
        q1 = db.query(User).filter(User.id == user_id_1)
        print("\n[Query eq UUID] Filters:", q1.filters)
        res1 = q1.first()
        assert res1 is not None
        assert res1.id == user_id_1
        
        # Test Operator: !=
        q2 = db.query(User).filter(User.email != "test_user1@example.com")
        print("[Query ne String] Filters:", q2.filters)
        res2 = q2.all()
        assert any(u.id == user_id_2 for u in res2)
        assert not any(u.id == user_id_1 for u in res2)
        
        # Test Operators: >, >=, <, <= against datetime fields
        q3 = db.query(User).filter(User.created_at > now)
        print("[Query gt Datetime] Filters:", q3.filters)
        res3 = [u for u in q3.all() if u.id in (user_id_1, user_id_2)]
        assert len(res3) == 1
        assert res3[0].id == user_id_2
        
        q4 = db.query(User).filter(User.created_at <= now)
        print("[Query le Datetime] Filters:", q4.filters)
        res4 = [u for u in q4.all() if u.id in (user_id_1, user_id_2)]
        assert len(res4) == 1
        assert res4[0].id == user_id_1
        
        # Test chained conditions (AND logic)
        q5 = db.query(User).filter(User.is_active == True, User.is_blocked == False, User.created_at > now)
        print("[Query Chained AND] Filters:", q5.filters)
        res5 = [u for u in q5.all() if u.id in (user_id_1, user_id_2)]
        assert len(res5) == 1
        assert res5[0].id == user_id_2

        # Test UUID byte-for-byte roundtrip
        q6 = db.query(User).filter(User.id == user_id_1)
        res6 = q6.first()
        assert str(res6.id) == str(user_id_1)
        print("[UUID Roundtrip] Original:", str(user_id_1), "Retrieved:", str(res6.id))
        
        # Test JSON field serialization/deserialization
        q7 = db.query(User).filter(User.id == user_id_1)
        res7 = q7.first()
        assert res7.metadata_json == {"role_info": {"level": 2}, "tags": ["test", "user1"]}
        print("[JSON Roundtrip] Retrieved metadata_json:", res7.metadata_json)

        # Test .order_by() on a field updated after insertion
        # Update user1's email/updated_at to make it sort differently
        user1.failed_login_attempts = 10
        user2.failed_login_attempts = 5
        db.add(user1)
        db.add(user2)
        db.commit()
        
        # Now query sorted by failed_login_attempts ascending
        q8 = db.query(User).filter(User.id.in_([user_id_1, user_id_2]) if hasattr(User.id, "in_") else (User.is_active == True)).order_by(User.failed_login_attempts.asc())
        print("[Query order_by asc] Sort:", q8.sort_field, "Dir:", q8.sort_dir)
        res8 = q8.all()
        # Find just our two users in the output
        our_users = [u for u in res8 if u.id in (user_id_1, user_id_2)]
        assert len(our_users) == 2
        assert our_users[0].id == user_id_2 # 5 < 10
        assert our_users[1].id == user_id_1

        # Now sort descending
        q9 = db.query(User).filter(User.is_active == True).order_by((User.failed_login_attempts.name, -1))
        print("[Query order_by desc] Sort:", q9.sort_field, "Dir:", q9.sort_dir)
        res9 = q9.all()
        our_users_desc = [u for u in res9 if u.id in (user_id_1, user_id_2)]
        assert len(our_users_desc) == 2
        assert our_users_desc[0].id == user_id_1 # 10 > 5
        assert our_users_desc[1].id == user_id_2
        
    finally:
        # Clean up
        db.delete(user1)
        db.delete(user2)
        db.commit()
