import logging

from fastapi import FastAPI, Request, status
from fastapi.exceptions import RequestValidationError
from fastapi.middleware.cors import CORSMiddleware
from fastapi.responses import JSONResponse
from slowapi.errors import RateLimitExceeded
from sqlalchemy.exc import IntegrityError

from app.api.routes import admin, ai, auth, blockchain, consent, issuer, verifier, wallet, zk
from app.core.config import settings
from app.core.rate_limit import limiter
from app.middleware.security_headers import CSRFProtectionMiddleware, SecurityHeadersMiddleware

logging.basicConfig(level=logging.INFO)
logger = logging.getLogger("decentra_id")

# NOTE: this logger configuration intentionally never logs request bodies,
# headers, or any PII — only structured, non-sensitive event metadata is
# ever emitted (see app/services/audit/logger.py for the durable audit
# trail, which is the authoritative record for compliance purposes).

app = FastAPI(
    title=settings.APP_NAME,
    version="1.0.0",
    description="Decentralized AI Identity Verification with Zero-Knowledge Authentication",
    docs_url="/api/docs" if settings.ENVIRONMENT != "production" else None,
    redoc_url=None,
)

app.state.limiter = limiter


@app.exception_handler(RateLimitExceeded)
async def rate_limit_handler(request: Request, exc: RateLimitExceeded):
    return JSONResponse(status_code=429, content={"detail": "Too many requests. Please slow down and try again shortly."})


@app.exception_handler(RequestValidationError)
async def validation_exception_handler(request: Request, exc: RequestValidationError):
    # Sanitized validation errors — never echoes raw submitted values
    # that could include sensitive data back into logs or responses.
    errors = [{"field": ".".join(str(p) for p in e["loc"]), "message": e["msg"]} for e in exc.errors()]
    return JSONResponse(status_code=422, content={"detail": "Validation failed.", "errors": errors})


@app.exception_handler(IntegrityError)
async def integrity_error_handler(request: Request, exc: IntegrityError):
    logger.warning("Database integrity error on %s %s", request.method, request.url.path)
    return JSONResponse(status_code=409, content={"detail": "The request conflicts with existing data."})


@app.exception_handler(Exception)
async def unhandled_exception_handler(request: Request, exc: Exception):
    # Generic 500 — never leaks stack traces or internal details to clients.
    logger.exception("Unhandled exception on %s %s", request.method, request.url.path)
    return JSONResponse(status_code=500, content={"detail": "An unexpected error occurred."})


app.add_middleware(
    CORSMiddleware,
    allow_origins=settings.ALLOWED_ORIGINS,
    allow_credentials=True,
    allow_methods=["GET", "POST", "PUT", "PATCH", "DELETE"],
    allow_headers=["Authorization", "Content-Type", "X-CSRF-Token"],
)
app.add_middleware(CSRFProtectionMiddleware)
app.add_middleware(SecurityHeadersMiddleware)


@app.get("/api/health", tags=["health"])
def health_check():
    return {"status": "ok", "service": settings.APP_NAME}


app.include_router(auth.router, prefix=settings.API_V1_PREFIX)
app.include_router(wallet.router, prefix=settings.API_V1_PREFIX)
app.include_router(issuer.router, prefix=settings.API_V1_PREFIX)
app.include_router(verifier.router, prefix=settings.API_V1_PREFIX)
app.include_router(consent.router, prefix=settings.API_V1_PREFIX)
app.include_router(ai.router, prefix=settings.API_V1_PREFIX)
app.include_router(admin.router, prefix=settings.API_V1_PREFIX)
app.include_router(blockchain.router, prefix=settings.API_V1_PREFIX)
app.include_router(zk.router, prefix=settings.API_V1_PREFIX)
