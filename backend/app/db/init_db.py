"""
Dev/CI convenience: creates all tables directly from the SQLAlchemy
metadata. In a real production rollout, use Alembic migrations
(`alembic upgrade head`) instead of `create_all` so schema changes are
versioned and reversible.
"""
from app.db.base import Base
from app.db.session import engine
import app.models  # noqa: F401  (ensures every model is registered on Base.metadata)


def init_db() -> None:
    Base.metadata.create_all(bind=engine)


if __name__ == "__main__":
    init_db()
    print("Database schema created.")
