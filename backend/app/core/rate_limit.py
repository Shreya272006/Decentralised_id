"""
Global and per-route rate limiting to mitigate brute-force auth attacks,
AI endpoint abuse, and verification spamming. Backed by Redis so limits
are enforced consistently across multiple API instances.
"""
from slowapi import Limiter
from slowapi.util import get_remote_address

from app.core.config import settings


def _client_key(request) -> str:
    """
    Rate-limit by authenticated user id when available (from a prior
    auth middleware setting request.state.user_id), falling back to
    remote IP for unauthenticated endpoints such as /auth/login.
    """
    user_id = getattr(request.state, "user_id", None)
    if user_id:
        return f"user:{user_id}"
    return f"ip:{get_remote_address(request)}"


limiter = Limiter(
    key_func=_client_key,
    storage_uri=settings.REDIS_URL,
    default_limits=[settings.RATE_LIMIT_DEFAULT],
    headers_enabled=True,
)
