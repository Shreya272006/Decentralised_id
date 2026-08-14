"""
Adds defense-in-depth HTTP security headers to every response and
enforces a double-submit-cookie CSRF check on state-changing requests
that are NOT authenticated purely via a Bearer token (i.e. any future
cookie-based session flow). Bearer-token API calls are inherently not
vulnerable to classic CSRF (no ambient credential is sent automatically
by the browser), but the check is included so the same backend safely
supports a future cookie-based web session without additional work.
"""
from starlette.middleware.base import BaseHTTPMiddleware
from starlette.requests import Request
from starlette.responses import Response

SAFE_METHODS = {"GET", "HEAD", "OPTIONS"}


class SecurityHeadersMiddleware(BaseHTTPMiddleware):
    async def dispatch(self, request: Request, call_next) -> Response:
        response = await call_next(request)
        response.headers["X-Content-Type-Options"] = "nosniff"
        response.headers["X-Frame-Options"] = "DENY"
        response.headers["Referrer-Policy"] = "strict-origin-when-cross-origin"
        response.headers["Permissions-Policy"] = "geolocation=(), camera=(), microphone=()"
        response.headers["Content-Security-Policy"] = "default-src 'none'; frame-ancestors 'none'"
        response.headers["Strict-Transport-Security"] = "max-age=63072000; includeSubDomains; preload"
        response.headers.setdefault("X-Permitted-Cross-Domain-Policies", "none")
        return response


class CSRFProtectionMiddleware(BaseHTTPMiddleware):
    """
    Double-submit cookie CSRF defense: if a `csrf_token` cookie is present
    (set only for cookie-session flows), state-changing requests must echo
    the same value in an `X-CSRF-Token` header. Pure Bearer-token requests
    (no session cookie present) are unaffected.
    """

    async def dispatch(self, request: Request, call_next) -> Response:
        if request.method not in SAFE_METHODS:
            cookie_token = request.cookies.get("csrf_token")
            if cookie_token:
                header_token = request.headers.get("x-csrf-token")
                if not header_token or header_token != cookie_token:
                    from starlette.responses import JSONResponse

                    return JSONResponse(status_code=403, content={"detail": "CSRF token missing or invalid."})
        return await call_next(request)
