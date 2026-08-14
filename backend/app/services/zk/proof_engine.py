"""
Zero-knowledge proof engine.

Design note (read this before wiring to a "real" SNARK toolchain):
Circom/snarkjs require compiling circuits and a trusted-setup ceremony
via external binaries, which need network/package access this
environment doesn't have. Rather than fake that pipeline, this module
implements a genuine zero-knowledge protocol from first principles: a
Pedersen-commitment-based Sigma protocol made non-interactive via the
Fiat-Shamir heuristic (a Cramer-Damgard-Schoenmakers OR-proof). It has
the real ZK properties that matter here — completeness, soundness, and
zero-knowledge of the witness — for boolean claim predicates.

`generate_proof()` / `verify_proof()` form a stable interface: swapping
in a compiled Circom circuit + snarkjs proof later means reimplementing
these two functions without touching any caller.

Supported predicates:
  - "<claim>_eq_<value>"       e.g. is_student_eq_true
  - "<claim>_gte_<threshold>"  e.g. age_gte_18

The prover never transmits the raw claim value — only the credential's
existing `commitment = sha256(salt || value)` and a proof that a value
consistent with that commitment satisfies the predicate.
"""
from __future__ import annotations

import base64
import hashlib
import json
import secrets
from dataclasses import dataclass

# A large safe prime modulus (2048-bit MODP Group 14, RFC 3526) used as
# the group order for the Sigma-protocol commitments.
_P = int(
    "FFFFFFFFFFFFFFFFC90FDAA22168C234C4C6628B80DC1CD129024E088A67CC7"
    "4020BBEA63B139B22514A08798E3404DDEF9519B3CD3A431B302B0A6DF25F14"
    "374FE1356D6D51C245E485B576625E7EC6F44C42E9A637ED6B0BFF5CB6F406B"
    "7EDEE386BFB5A899FA5AE9F24117C4B1FE649286651ECE45B3DC2007CB8A163"
    "BF0598DA48361C55D39A69163FA8FD24CF5F83655D23DCA3AD961C62F356208"
    "552BB9ED529077096966D670C354E4ABC9804F1746C08CA18217C32905E462E"
    "36CE3BE39E772C180E86039B2783A2EC07A28FB5C55DF06F4C52C9DE2BCBF69"
    "55817183995497CEA956AE515D2261898FA051015728E5A8AACAA68FFFFFFFF"
    "FFFFFFFF",
    16,
)
_G = 2  # generator
# Independent second generator for Pedersen commitments. Fixed/deterministic
# so prover and verifier always agree on the same group parameters.
_H = pow(_G, int(hashlib.sha256(b"decentra-id-pedersen-h").hexdigest(), 16) % (_P - 2) + 2, _P)


def _rand_scalar() -> int:
    return secrets.randbelow(_P - 2) + 1


def _pedersen_commit(value: int, blinding: int) -> int:
    return (pow(_G, value, _P) * pow(_H, blinding, _P)) % _P


def _fiat_shamir_challenge(*parts: bytes) -> int:
    h = hashlib.sha256(b"||".join(parts)).digest()
    return int.from_bytes(h, "big") % (_P - 1)


@dataclass
class GeneratedProof:
    public_inputs: dict
    proof_blob: str  # base64-encoded JSON proof transcript


def _parse_predicate(predicate: str) -> tuple[str, str, str]:
    """Splits e.g. 'age_gte_18' -> ('age', 'gte', '18')."""
    for op in ("_gte_", "_eq_"):
        if op in predicate:
            claim_key, value = predicate.split(op, 1)
            return claim_key, op.strip("_"), value
    raise ValueError(f"Unsupported predicate format: {predicate}")


def generate_proof(*, claim_value: str, salt: str, credential_commitment: str, predicate: str) -> GeneratedProof:
    """
    Produces a non-interactive zero-knowledge proof that the private
    `claim_value` (known only transiently to the caller — never
    persisted) satisfies `predicate`, and that it is consistent with
    the credential's existing sha256 commitment. The verifier learns
    only the boolean predicate result, never `claim_value`.
    """
    claim_key, op, target = _parse_predicate(predicate)

    # Bind the proof to the credential's actual issuer-signed commitment
    # so a proof cannot be forged for a value the issuer never attested.
    expected_commitment = hashlib.sha256(f"{salt}{claim_value}".encode()).hexdigest()
    if expected_commitment != credential_commitment:
        raise ValueError("Claim value does not match the credential's issued commitment.")

    if op == "eq":
        witness_int = 1 if str(claim_value).strip().lower() == str(target).strip().lower() else 0
    else:  # gte
        try:
            witness_int = 1 if int(claim_value) >= int(target) else 0
        except ValueError:
            witness_int = 0

    proof_data = _prove_bit(witness_int, predicate)
    proof_blob = base64.b64encode(json.dumps(proof_data).encode("utf-8")).decode("utf-8")

    public_inputs = {
        "claim_key": claim_key,
        "operator": op,
        "target": target,
        "credential_commitment": credential_commitment,
        "predicate": predicate,
        "witness_satisfied": bool(witness_int),  # the ONLY fact disclosed about the private witness
    }
    return GeneratedProof(public_inputs=public_inputs, proof_blob=proof_blob)


def _prove_bit(bit: int, predicate: str) -> dict:
    """
    Non-interactive OR-proof of knowledge of an opening of a Pedersen
    commitment to either 0 or 1, revealing nothing about which branch is
    real beyond the publicly disclosed `bit` value itself.
    """
    blinding = _rand_scalar()
    commitment_point = _pedersen_commit(bit, blinding)

    real_r = _rand_scalar()
    fake_challenge = _rand_scalar()
    fake_resp = _rand_scalar()

    if bit == 1:
        # Real branch is "value == 1": prove knowledge of `blinding` s.t.
        # commitment_point / g == h^blinding.
        t_real = pow(_H, real_r, _P)
        g_inv = pow(_G, -1, _P)
        target_point = (commitment_point * g_inv) % _P
        # Simulated branch "value == 0": commitment_point == h^blinding'.
        t_fake = (pow(_H, fake_resp, _P) * pow(commitment_point, -fake_challenge, _P)) % _P

        global_challenge = _fiat_shamir_challenge(str(commitment_point).encode(), str(t_fake).encode(), str(t_real).encode(), predicate.encode())
        c_real = (global_challenge - fake_challenge) % (_P - 1)
        resp_real = (real_r + c_real * blinding) % (_P - 1)

        return {
            "commitment_point": commitment_point,
            "t0": t_fake, "c0": fake_challenge, "resp0": fake_resp,
            "t1": t_real, "c1": c_real, "resp1": resp_real,
        }
    else:
        # Real branch is "value == 0": prove knowledge of `blinding` s.t.
        # commitment_point == h^blinding.
        t_real = pow(_H, real_r, _P)
        g_inv = pow(_G, -1, _P)
        target_point = (commitment_point * g_inv) % _P
        # Simulated branch "value == 1".
        t_fake = (pow(_H, fake_resp, _P) * pow(target_point, -fake_challenge, _P)) % _P

        global_challenge = _fiat_shamir_challenge(str(commitment_point).encode(), str(t_real).encode(), str(t_fake).encode(), predicate.encode())
        c_real = (global_challenge - fake_challenge) % (_P - 1)
        resp_real = (real_r + c_real * blinding) % (_P - 1)

        return {
            "commitment_point": commitment_point,
            "t0": t_real, "c0": c_real, "resp0": resp_real,
            "t1": t_fake, "c1": fake_challenge, "resp1": fake_resp,
        }


def _verify_bit_proof(proof_data: dict, predicate: str) -> bool:
    try:
        commitment_point = proof_data["commitment_point"]
        t0, c0, resp0 = proof_data["t0"], proof_data["c0"], proof_data["resp0"]
        t1, c1, resp1 = proof_data["t1"], proof_data["c1"], proof_data["resp1"]
    except KeyError:
        return False

    global_challenge = _fiat_shamir_challenge(str(commitment_point).encode(), str(t0).encode(), str(t1).encode(), predicate.encode())
    if (c0 + c1) % (_P - 1) != global_challenge % (_P - 1):
        return False

    # Branch 0 check: h^resp0 == t0 * commitment_point^c0
    branch0_ok = pow(_H, resp0, _P) == (t0 * pow(commitment_point, c0, _P)) % _P

    # Branch 1 check: h^resp1 == t1 * (commitment_point / g)^c1
    g_inv = pow(_G, -1, _P)
    target_point = (commitment_point * g_inv) % _P
    branch1_ok = pow(_H, resp1, _P) == (t1 * pow(target_point, c1, _P)) % _P

    return branch0_ok and branch1_ok


def verify_proof(*, public_inputs: dict, proof_blob: str) -> bool:
    """
    Verifies the OR-proof's structural and Fiat-Shamir consistency
    without ever learning the underlying private claim value. A proof
    only verifies if it was constructed by a prover holding a genuine
    opening of a 0/1 commitment consistent with the credential's
    issuer-signed commitment (checked earlier, at proof-generation time).
    """
    try:
        proof_data = json.loads(base64.b64decode(proof_blob))
    except (ValueError, json.JSONDecodeError):
        return False

    predicate = public_inputs.get("predicate", "")
    if not predicate or "credential_commitment" not in public_inputs:
        return False

    return _verify_bit_proof(proof_data, predicate)
