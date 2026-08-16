import sys
from types import ModuleType

# Patch bcrypt to fix the passlib ValueError bug (password length check)
try:
    import bcrypt
    _original_hashpw = bcrypt.hashpw
    def _patched_hashpw(password, salt):
        if isinstance(password, str):
            password = password.encode('utf-8')
        if len(password) > 72:
            password = password[:72]
        return _original_hashpw(password, salt)
    bcrypt.hashpw = _patched_hashpw
except ImportError:
    pass

class CountShim:
    def __init__(self, field_shim):
        self.field_shim = field_shim
        self.model_class = getattr(field_shim, "model_class", None)
        self.is_count = True

class DistinctShim:
    def __init__(self, field_shim):
        self.field_shim = field_shim
        self.model_class = getattr(field_shim, "model_class", None)

class DummyFunc:
    def count(self, arg):
        if isinstance(arg, DistinctShim):
            return CountShim(arg.field_shim)
        return CountShim(arg)
        
    def distinct(self, arg):
        return DistinctShim(arg)

sqlalchemy = ModuleType("sqlalchemy")
sqlalchemy_orm = ModuleType("sqlalchemy.orm")
sqlalchemy_exc = ModuleType("sqlalchemy.exc")

sqlalchemy.func = DummyFunc()
sqlalchemy_orm.Session = object
sqlalchemy_exc.IntegrityError = Exception

sys.modules["sqlalchemy"] = sqlalchemy
sys.modules["sqlalchemy.orm"] = sqlalchemy_orm
sys.modules["sqlalchemy.exc"] = sqlalchemy_exc
