# Cryptographic & Contract Audit Preparation

This document outlines the cryptographic primitives, zero-knowledge proofs, and smart contract structures in use in DecentraID to prepare for an external security audit.

---

## 1. Zero-Knowledge Proof Cryptosystem

DecentraID implements a non-interactive zero-knowledge OR-proof of knowledge (a Sigma protocol compiled via the Fiat-Shamir heuristic) to prove predicates over credential claims without disclosing raw claim values.

### Pedersen Commitments
To blind the private claim value $v$ and ensure hiding and binding properties, we commit to the value using two generators $G$ and $H$ in a finite cyclic group of safe prime order $P$:

$$C = G^v \cdot H^r \pmod P$$

- **Group Parameters**: We use a 2048-bit safe prime modulus $P$ (MODP Group 14 from RFC 3526) as the group order.
- **Generators**: 
  - $G = 2$
  - $H$ is a deterministically derived generator computed via:
    $$H = G^{\text{sha256("decentra-id-pedersen-h")} \pmod{P-2} + 2} \pmod P$$
- **Blinding Factor**: $r$ is a random scalar generated in $[1, P-2]$.

### Fiat-Shamir Heuristic (OR-Proof / CDS Protocol)
To prove that $v \in \{0, 1\}$ (a boolean bit or satisfying predicate) without revealing which value is committed:
1. The prover constructs two branches (one real, one simulated):
   - **Real Branch**: Proves knowledge of the discrete log $r$ of $C / G^v$ base $H$.
   - **Simulated Branch**: Simulates a valid transcript $(t, c, resp)$ using randomly chosen challenge $c$ and response $resp$.
2. The interactive challenge is replaced by a Fiat-Shamir non-interactive challenge computed by hashing the commitment point, simulated commitments, and the predicate string:
   $$c_{total} = \text{hash}(C \parallel t_0 \parallel t_1 \parallel \text{predicate}) \pmod{P-1}$$
3. The total challenge is split such that $c_0 + c_1 = c_{total} \pmod{P-1}$, verifying that the prover knows the witness for at least one branch.

---

## 2. CSPRNG Randomness Audit

A systematic scan of `backend/app/services/zk/proof_engine.py` was conducted to ensure no weak pseudorandom number generators (like Python's standard `random` library) are used. 

* **Random Generation Vector**: Random scalars $r$ are generated strictly via `_rand_scalar()`:
  ```python
  def _rand_scalar() -> int:
      return secrets.randbelow(_P - 2) + 1
  ```
* **Security Verification**: Python's `secrets` module utilizes the operating system's Cryptographically Secure Pseudorandom Number Generator (CSPRNG), satisfying standard cryptographic randomness requirements. No use of weak RNGs (e.g. `random.randint` or `random.random`) exists.

---

## 3. Smart Contract Review

A static analysis and manual code review of the three Solidity contracts (`CredentialRegistry.sol`, `IssuerRegistry.sol`, `RevocationRegistry.sol`) was performed.

### Findings & Security Considerations
1. **Access Control**: Roles (`BACKEND_SERVICE_ROLE`, `PLATFORM_ADMIN_ROLE`) are securely controlled using OpenZeppelin's `AccessControl` contract. Critical state changes (e.g. `anchorRecord`) are restricted.
2. **Reentrancy**: Modifiers from `ReentrancyGuard` (`nonReentrant`) are correctly applied to prevent reentrancy vectors.
3. **Pausability**: Critical write functions check the `whenNotPaused` condition. Pausing and unpausing are restricted to `PLATFORM_ADMIN_ROLE`.
4. **Data Privacy**: The design limits on-chain storage to cryptographic hashes and commitments, successfully avoiding any leakage of raw Personally Identifiable Information (PII) on the ledger.
5. **Idempotence**: `anchorRecord` in `CredentialRegistry` prevents double-anchoring the same credential reference by checking `!_credentials[referenceId].exists`.
