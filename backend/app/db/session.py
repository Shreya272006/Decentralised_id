import uuid
import copy
from datetime import datetime
from pymongo import MongoClient
from app.core.config import settings
from app.db.base import FieldShim

client = MongoClient(settings.DATABASE_URL)
db_name = settings.DATABASE_URL.split("/")[-1].split("?")[0] or "did_platform"
mongodb = client[db_name]

class QueryShim:
    def __init__(self, model, session_shim):
        self.session = session_shim
        self.db = session_shim.db
        self.project_field = None
        self.is_count = False
        
        # Detect field projections or counts
        if isinstance(model, FieldShim):
            self.project_field = model.name
            self.model = model.model_class
        elif hasattr(model, "is_count") and model.is_count:
            self.is_count = True
            self.model = model.model_class
        else:
            self.model = model
            
        tablename = getattr(self.model, "__tablename__", self.model.__name__.lower())
        self.collection = self.db[tablename]
        self.filters = {}
        self.sort_field = None
        self.sort_dir = 1
        self.limit_val = None
        self.offset_val = None

    def filter(self, *criterion):
        for crit in criterion:
            if isinstance(crit, tuple) and len(crit) == 3:
                name, val, op = crit
                if isinstance(val, uuid.UUID):
                    val = str(val)
                elif isinstance(val, datetime):
                    val = val.isoformat()
                # Map operations
                if op == "eq":
                    self.filters[name] = val
                elif op == "ne":
                    self.filters[name] = {"$ne": val}
                elif op == "ge":
                    self.filters[name] = {"$gte": val}
                elif op == "le":
                    self.filters[name] = {"$lte": val}
                elif op == "gt":
                    self.filters[name] = {"$gt": val}
                elif op == "lt":
                    self.filters[name] = {"$lt": val}
        return self

    def order_by(self, crit):
        if isinstance(crit, FieldShim):
            self.sort_field = crit.name
            self.sort_dir = 1
        elif isinstance(crit, tuple) and len(crit) == 2:
            self.sort_field, self.sort_dir = crit
        return self

    def limit(self, val):
        self.limit_val = val
        return self

    def offset(self, val):
        self.offset_val = val
        return self

    def _execute(self):
        cursor = self.collection.find(self.filters)
        if self.sort_field:
            cursor = cursor.sort(self.sort_field, self.sort_dir)
        if self.offset_val is not None:
            cursor = cursor.skip(self.offset_val)
        if self.limit_val is not None:
            cursor = cursor.limit(self.limit_val)
        return cursor

    def first(self):
        res = list(self.limit(1)._execute())
        if res:
            obj = self.model.from_dict(res[0])
            if hasattr(self.session, "tracked"):
                self.session.tracked[obj.id] = (obj, copy.deepcopy(obj.to_dict()))
            if self.project_field:
                return (getattr(obj, self.project_field),)
            return obj
        return None

    def all(self):
        res = list(self._execute())
        objs = []
        for doc in res:
            obj = self.model.from_dict(doc)
            if hasattr(self.session, "tracked"):
                self.session.tracked[obj.id] = (obj, copy.deepcopy(obj.to_dict()))
            objs.append(obj)
        if self.project_field:
            return [(getattr(obj, self.project_field),) for obj in objs]
        return objs

    def count(self):
        return self.collection.count_documents(self.filters)

    def scalar(self):
        if self.is_count:
            return self.count()
        res = list(self.limit(1)._execute())
        if res:
            obj = self.model.from_dict(res[0])
            if hasattr(self.session, "tracked"):
                self.session.tracked[obj.id] = (obj, copy.deepcopy(obj.to_dict()))
            if self.project_field:
                return getattr(obj, self.project_field)
            return obj
        return None


class SessionShim:
    def __init__(self, db):
        self.db = db
        self.pending = []
        self.tracked = {}

    def query(self, model, *args, **kwargs):
        return QueryShim(model, self)

    def add(self, obj):
        self.pending.append(obj)

    def commit(self):
        # Automatically include all tracked objects that have been queried and modified,
        # but deduplicate by ID so that manually added instances take precedence.
        pending_ids = {str(getattr(obj, "id", None)) for obj in self.pending if getattr(obj, "id", None) is not None}
        for obj, snapshot in self.tracked.values():
            if obj.to_dict() != snapshot:
                obj_id = str(obj.id)
                if obj_id not in pending_ids:
                    self.pending.append(obj)
        if not self.pending:
            return
        try:
            # Attempt to use a MongoDB transaction session if supported by topology
            with self.db.client.start_session() as session:
                with session.start_transaction():
                    for obj in self.pending:
                        tablename = getattr(obj, "__tablename__", obj.__class__.__name__.lower())
                        collection = self.db[tablename]
                        doc = obj.to_dict()
                        collection.replace_one({"_id": doc["_id"]}, doc, upsert=True, session=session)
            self.pending.clear()
            self.tracked.clear()
        except Exception:
            # Fallback for standalone or if transaction fails
            for obj in self.pending:
                tablename = getattr(obj, "__tablename__", obj.__class__.__name__.lower())
                collection = self.db[tablename]
                doc = obj.to_dict()
                collection.replace_one({"_id": doc["_id"]}, doc, upsert=True)
            self.pending.clear()
            self.tracked.clear()

    def refresh(self, obj):
        tablename = getattr(obj, "__tablename__", obj.__class__.__name__.lower())
        collection = self.db[tablename]
        doc = collection.find_one({"_id": str(obj.id)})
        if doc:
            for k, v in obj.from_dict(doc).__dict__.items():
                setattr(obj, k, v)

    def delete(self, obj):
        tablename = getattr(obj, "__tablename__", obj.__class__.__name__.lower())
        collection = self.db[tablename]
        collection.delete_one({"_id": str(obj.id)})

    def flush(self):
        self.commit()

    def rollback(self):
        self.pending.clear()
        self.tracked.clear()

    def close(self):
        self.pending.clear()
        self.tracked.clear()


SessionLocal = lambda: SessionShim(mongodb)


def get_db():
    db = SessionShim(mongodb)
    try:
        yield db
    finally:
        db.close()
