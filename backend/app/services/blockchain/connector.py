"""
Blockchain connector — anchors credential issuance/revocation hashes
(never raw PII) to the on-chain registries defined in /contracts.

Uses web3.py against any EVM-compatible RPC endpoint (local Hardhat
node in dev, a testnet/mainnet RPC in production). Transactions are
signed server-side with a dedicated operational key that only has
permission to call the registry contracts' anchor functions — never a
user-custodied key.
"""
from __future__ import annotations

import json
import os
from dataclasses import dataclass
from pathlib import Path

from eth_account import Account
from web3 import Web3

try:
    from web3.middleware import geth_poa_middleware
except ImportError:
    # For web3.py 7.x compatibility
    try:
        from web3.middleware.proof_of_authority import ExtraDataToPOAMiddleware as geth_poa_middleware
    except ImportError:
        # Fallback: create a dummy middleware
        geth_poa_middleware = None

from app.core.config import settings

_ABI_DIR = Path(__file__).resolve().parents[3] / "contracts_abi"


@dataclass
class AnchorResult:
    tx_hash: str
    block_number: int | None
    confirmed: bool


def _load_abi(name: str) -> list:
    path = _ABI_DIR / f"{name}.json"
    if not path.exists():
        # Minimal fallback ABI covering only the functions this connector
        # calls, so the service remains importable/testable before the
        # compiled Hardhat artifacts are copied into contracts_abi/.
        return _fallback_abi(name)
    with open(path) as f:
        return json.load(f)["abi"]


def _fallback_abi(name: str) -> list:
    common_anchor_fn = {
        "inputs": [
            {"internalType": "bytes32", "name": "recordHash", "type": "bytes32"},
            {"internalType": "bytes32", "name": "referenceId", "type": "bytes32"},
        ],
        "name": "anchorRecord",
        "outputs": [],
        "stateMutability": "nonpayable",
        "type": "function",
    }
    read_fn = {
        "inputs": [{"internalType": "bytes32", "name": "referenceId", "type": "bytes32"}],
        "name": "getRecord",
        "outputs": [
            {"internalType": "bytes32", "name": "recordHash", "type": "bytes32"},
            {"internalType": "bool", "name": "exists", "type": "bool"},
        ],
        "stateMutability": "view",
        "type": "function",
    }
    return [common_anchor_fn, read_fn]


class BlockchainConnector:
    def __init__(self):
        self.w3 = Web3(Web3.HTTPProvider(settings.WEB3_PROVIDER_URL))
        if geth_poa_middleware:
            self.w3.middleware_onion.inject(geth_poa_middleware, layer=0)
        self.account = (
            Account.from_key(settings.DEPLOYER_PRIVATE_KEY) if settings.DEPLOYER_PRIVATE_KEY else None
        )

    def _contract(self, address: str, abi_name: str):
        return self.w3.eth.contract(address=Web3.to_checksum_address(address), abi=_load_abi(abi_name))

    def _send(self, contract, fn_name: str, *args) -> AnchorResult:
        if self.account is None:
            raise RuntimeError("DEPLOYER_PRIVATE_KEY is not configured; cannot sign blockchain transactions.")

        fn = getattr(contract.functions, fn_name)(*args)
        nonce = self.w3.eth.get_transaction_count(self.account.address, "pending")
        tx = fn.build_transaction(
            {
                "chainId": settings.CHAIN_ID,
                "from": self.account.address,
                "nonce": nonce,
                "gas": 300_000,
                "maxFeePerGas": self.w3.to_wei("30", "gwei"),
                "maxPriorityFeePerGas": self.w3.to_wei("2", "gwei"),
            }
        )
        signed = self.account.sign_transaction(tx)
        tx_hash = self.w3.eth.send_raw_transaction(signed.raw_transaction)
        receipt = self.w3.eth.wait_for_transaction_receipt(tx_hash, timeout=120)

        return AnchorResult(
            tx_hash=tx_hash.hex(),
            block_number=receipt.blockNumber,
            confirmed=receipt.status == 1,
        )

    def anchor_credential(self, credential_id: str, record_hash_hex: str) -> AnchorResult:
        contract = self._contract(settings.CREDENTIAL_REGISTRY_ADDRESS, "CredentialRegistry")
        reference_id = Web3.keccak(text=credential_id)
        record_hash = bytes.fromhex(record_hash_hex.removeprefix("0x"))
        return self._send(contract, "anchorRecord", record_hash, reference_id)

    def anchor_revocation(self, credential_id: str, record_hash_hex: str) -> AnchorResult:
        contract = self._contract(settings.REVOCATION_REGISTRY_ADDRESS, "RevocationRegistry")
        reference_id = Web3.keccak(text=credential_id)
        record_hash = bytes.fromhex(record_hash_hex.removeprefix("0x"))
        return self._send(contract, "anchorRecord", record_hash, reference_id)

    def register_issuer(self, issuer_profile_id: str, record_hash_hex: str) -> AnchorResult:
        contract = self._contract(settings.ISSUER_REGISTRY_ADDRESS, "IssuerRegistry")
        reference_id = Web3.keccak(text=issuer_profile_id)
        record_hash = bytes.fromhex(record_hash_hex.removeprefix("0x"))
        return self._send(contract, "anchorRecord", record_hash, reference_id)

    def is_connected(self) -> bool:
        try:
            return self.w3.is_connected()
        except Exception:
            return False


blockchain_connector = BlockchainConnector()
