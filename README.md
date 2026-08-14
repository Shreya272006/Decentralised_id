# DecentraID — Decentralized AI Identity Verification with Zero-Knowledge Authentication

Prove sensitive claims — age, student status, employment, KYC validity — without exposing
raw personal data. Combines decentralized identity (DIDs), AI-based fraud detection,
zero-knowledge proofs, granular consent management, and a tamper-evident audit trail.

> **Read this before you demo it.** This is a hackathon-grade reference implementation, not
> an audited production system. Two things in particular are deliberately built as
> from-scratch reference implementations rather than wrapping a heavier third-party toolchain,
> because this environment has no package-registry/network access:
>
> 1. **The ZK proof engine** (`backend/app/services/zk/proof_engine.py`) is a real,
>    working, tested Sigma-protocol (Pedersen commitments + Fiat-Shamir OR-proof), not a
>    Circom/snarkjs circuit. It has genuine zero-knowledge properties for the boolean
>    predicates this app needs (`age_gte_18`, `is_student_eq_true`, etc.). Swapping in a
>    compiled SNARK circuit later only requires reimplementing `generate_proof()` /
>    `verify_proof()` — no caller changes.
> 2. **The AI pipeline** (`backend/app/services/ai/`) uses classical OpenCV/Tesseract
>    techniques (noise-variance/edge/copy-move tamper heuristics, HOG-based face similarity,
>    multi-frame liveness heuristics) instead of downloaded deep-learning model weights.
>    Swap `_extract_embedding()` and `analyze_document()` for real model inference behind
>    the same function signatures for production use.
>
> Before any real deployment: get an independent security audit (especially of the smart
> contracts and the ZK engine), replace the HMAC-based issuer "signature" placeholder with
> real Ed25519/ECDSA signing backed by a KMS/HSM, and move JWTs to httpOnly cookies.

---

## Architecture

```
decentra-id/
├── backend/            FastAPI, SQLAlchemy, Pydantic, AI pipeline, ZK engine, blockchain connector
├── contracts/          Solidity (CredentialRegistry, RevocationRegistry, IssuerRegistry) + Hardhat
├── frontend/            Next.js App Router + Tailwind CSS dashboards
├── docker-compose.yml
└── .env.example
```

**Backend**: JWT auth with TOTP-based MFA and account lockout, AES-256-GCM field encryption,
RBAC with per-object ownership checks (IDOR prevention), Redis-backed rate limiting on every
auth/AI/verification endpoint, and a hash-chained tamper-evident audit log.

**AI pipeline**: OCR text extraction + multi-signal document tamper detection, face-match
similarity scoring, multi-frame liveness heuristics, and a weighted fraud-risk aggregator
producing `APPROVED` / `REVIEW` / `REJECTED`.

**ZK module**: Non-interactive zero-knowledge proofs (Pedersen commitment + Fiat-Shamir
OR-proof) that a credential's committed claim satisfies a predicate (`age_gte_18`,
`is_student_eq_true`, ...) without revealing the underlying value.

**Blockchain**: Three Solidity contracts using OpenZeppelin `AccessControl` — only
cryptographic hashes and booleans are ever anchored on-chain, never PII.

**Frontend**: Public landing/how-it-works/privacy pages, auth screens, and four role-scoped
dashboards (User wallet, Issuer console, Verifier terminal, Admin console) with charts,
consent modals, and status badges.

---

## Running locally with Docker Compose

### 1. Prerequisites
- Docker and Docker Compose installed
- Ports `3000`, `8000`, `5432`, `6379`, `8545` free

### 2. Configure environment
```bash
cp .env.example .env
# Edit .env and set real values for JWT_SECRET_KEY and FIELD_ENCRYPTION_KEY:
python3 -c "import secrets; print(secrets.token_urlsafe(64))"   # -> JWT_SECRET_KEY
python3 -c "import secrets; print(secrets.token_urlsafe(32))"   # -> FIELD_ENCRYPTION_KEY
```

### 3. Start the stack
```bash
docker-compose up --build
```
This brings up Postgres, Redis, a local Hardhat blockchain node, the FastAPI backend, and the
Next.js frontend.

### 4. Deploy the smart contracts (first run only)
In a separate terminal, once `hardhat-node` is healthy:
```bash
docker-compose exec hardhat-node npx hardhat run scripts/deploy.js --network localhost
```
Copy the three printed contract addresses into your `.env` as `CREDENTIAL_REGISTRY_ADDRESS`,
`REVOCATION_REGISTRY_ADDRESS`, and `ISSUER_REGISTRY_ADDRESS`, then:
```bash
docker-compose restart backend
```

### 5. Initialize and seed the database
```bash
docker-compose exec backend python -m scripts.seed_db
```
This creates the schema and seeds demo accounts:

| Role     | Email                       | Password           | Notes                                     |
|----------|------------------------------|---------------------|--------------------------------------------|
| Admin    | admin@decentraid.dev         | AdminPass!2024      |                                              |
| Issuer   | issuer@university.edu        | IssuerPass!2024     | Pre-approved                                |
| Verifier | verifier@bar-nightclub.com   | VerifierPass!2024   |                                              |
| User     | alice@example.com            | AlicePass!2024      | Has `age_verification` + `student_status`   |
| User     | bob@example.com              | BobPass!2024        | Has an under-18 `age_verification`          |

### 6. Open the app
- Frontend: http://localhost:3000
- API docs (Swagger): http://localhost:8000/api/docs
- API health check: http://localhost:8000/api/health

---

## Demo flow

1. Log in as **Alice** → Wallet tab → generate a proof for `age_gte_18` on her
   `age_verification` credential. Copy the returned `zk_proof_id`.
2. Log in as the **Verifier** → Proof Request Builder → send a request to
   `alice@example.com` for scope `age_gte_18`. Copy the returned `consent_id`.
3. Log back in as **Alice** → Consent History tab → approve the pending request.
4. Log back in as the **Verifier** → Verification Terminal → paste the `consent_id` and
   `zk_proof_id` → Verify. Result: `valid` — without ever seeing Alice's date of birth.
5. Log in as the **Admin** → System Health tab → confirm the audit log chain integrity
   check reports `intact: true`.

---

## Running without Docker (local dev)

**Backend**
```bash
cd backend
python3 -m venv .venv && source .venv/bin/activate
pip install -r requirements.txt
# Start Postgres and Redis yourself, or point DATABASE_URL/REDIS_URL elsewhere
python -m scripts.seed_db
uvicorn app.main:app --reload
```

**Contracts**
```bash
cd contracts
npm install
npx hardhat node          # in one terminal
npx hardhat run scripts/deploy.js --network localhost   # in another
```

**Frontend**
```bash
cd frontend
npm install
npm run dev
```

---

## Security notes

- Every sensitive field (document images, extracted claim values, MFA secrets) is
  encrypted with AES-256-GCM before it touches the database or disk.
- Every protected route checks resource ownership, not just role membership, to prevent
  IDOR (see `assert_owner_or_role` in `app/core/rbac.py`).
- Rate limits are enforced per-user (falling back to per-IP) on auth, AI, and verification
  endpoints via `slowapi` + Redis.
- The audit log is hash-chained; `GET /api/admin/logs/integrity` replays and verifies the
  entire chain.
- CSRF double-submit-cookie protection and standard security headers (CSP, HSTS, X-Frame-
  Options, etc.) are applied to every response.
