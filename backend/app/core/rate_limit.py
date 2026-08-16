"""
Global and per-route rate limiting to mitigate brute-force auth attacks,
AI endpoint abuse, and verification spamming. Backed by Redis so limits
are enforced consistently across multiple API instances.
"""
from slowapi import Limiter
from slowapi.util import get_remote_address

from app.core.config import settings


import redis

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


storage_uri = settings.REDIS_URL
try:
    # Check if Redis is running, fallback to memory if not
    r = redis.from_url(settings.REDIS_URL, socket_connect_timeout=1)
    r.ping()
except Exception:
    # NOTE: memory:// fallback is per-process and won't share limits across multiple workers — single-worker only for now.
    storage_uri = "memory://"

limiter = Limiter(
    key_func=_client_key,
    storage_uri=storage_uri,
    default_limits=[settings.RATE_LIMIT_DEFAULT],
    headers_enabled=False,
)
