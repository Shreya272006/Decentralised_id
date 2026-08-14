from typing import TypeVar, Generic, Any
import uuid
from datetime import datetime

T = TypeVar('T')

class Mapped(Generic[T]):
    pass

def mapped_column(*args, **kwargs):
    return None

def relationship(*args, **kwargs):
    return None

class DummyType:
    def __init__(self, *args, **kwargs):
        pass

String = DummyType
Boolean = DummyType
DateTime = DummyType
ForeignKey = DummyType
SAEnum = DummyType
UUID = DummyType
JSONB = DummyType
ARRAY = DummyType
INET = DummyType
Integer = DummyType
Text = DummyType
Float = DummyType

class FieldShim:
    def __init__(self, name):
        self.name = name
    def __eq__(self, other):
        return (self.name, other, "eq")
    def __ne__(self, other):
        return (self.name, other, "ne")
    def __ge__(self, other):
        return (self.name, other, "ge")
    def __le__(self, other):
        return (self.name, other, "le")
    def __gt__(self, other):
        return (self.name, other, "gt")
    def __lt__(self, other):
        return (self.name, other, "lt")
    def desc(self):
        return (self.name, -1)
    def asc(self):
        return (self.name, 1)

class ModelMetaclass(type):
    def __new__(cls, name, bases, attrs):
        annotations = attrs.get("__annotations__", {})
        for field_name in annotations:
            if field_name not in attrs:
                attrs[field_name] = FieldShim(field_name)
        for base in bases:
            for field_name in getattr(base, "__annotations__", {}):
                if field_name not in attrs:
                    attrs[field_name] = FieldShim(field_name)
        new_class = super().__new__(cls, name, bases, attrs)
        for attr_name in dir(new_class):
            try:
                attr_val = getattr(new_class, attr_name)
                if isinstance(attr_val, FieldShim):
                    attr_val.model_class = new_class
            except AttributeError:
                pass
        return new_class

class Base(metaclass=ModelMetaclass):
    def __init__(self, **kwargs):
        for k, v in kwargs.items():
            setattr(self, k, v)
        if not hasattr(self, "id") or self.id is None:
            self.id = uuid.uuid4()
        if not hasattr(self, "created_at"):
            self.created_at = datetime.utcnow()
        if not hasattr(self, "updated_at"):
            self.updated_at = datetime.utcnow()

    def to_dict(self):
        d = {}
        for k, v in self.__dict__.items():
            if isinstance(v, uuid.UUID):
                d[k] = str(v)
            elif isinstance(v, datetime):
                d[k] = v.isoformat()
            elif isinstance(v, Base):
                pass
            elif k.startswith("_"):
                pass
            else:
                d[k] = v
        d["_id"] = str(self.id)
        d["id"] = str(self.id)
        return d

    @classmethod
    def from_dict(cls, d):
        if not d:
            return None
        obj = cls.__new__(cls)
        for k, v in d.items():
            if k == "_id":
                k = "id"
            if k == "id" and isinstance(v, str):
                try:
                    v = uuid.UUID(v)
                except ValueError:
                    pass
            elif k in ("created_at", "updated_at", "locked_until", "verified_at", "expires_at", "uploaded_at", "matched_at", "timestamp") and isinstance(v, str):
                try:
                    v = datetime.fromisoformat(v)
                except ValueError:
                    pass
            setattr(obj, k, v)
        return obj
