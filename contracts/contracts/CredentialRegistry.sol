// SPDX-License-Identifier: MIT
pragma solidity ^0.8.24;

import "@openzeppelin/contracts/access/AccessControl.sol";
import "@openzeppelin/contracts/utils/Pausable.sol";
import "@openzeppelin/contracts/utils/ReentrancyGuard.sol";
import "./IssuerRegistry.sol";

/// @title CredentialRegistry
/// @notice Anchors tamper-evident hashes of issued verifiable credentials.
///         Stores ONLY a sha256/keccak256 commitment of the credential's
///         claims — never raw personal data, exact dates of birth, ID
///         numbers, or document images. Anyone can verify a credential's
///         integrity by recomputing the commitment off-chain and comparing
///         it to the anchored hash.
contract CredentialRegistry is AccessControl, Pausable, ReentrancyGuard {
    bytes32 public constant BACKEND_SERVICE_ROLE = keccak256("BACKEND_SERVICE_ROLE");
    bytes32 public constant PLATFORM_ADMIN_ROLE = keccak256("PLATFORM_ADMIN_ROLE");

    struct CredentialRecord {
        bytes32 recordHash;   // commitment hash over the credential's claims
        bytes32 issuerRef;    // reference id of the issuing organization
        uint256 anchoredAt;
        bool exists;
    }

    IssuerRegistry public immutable issuerRegistry;

    mapping(bytes32 => CredentialRecord) private _credentials; // referenceId (credential id hash) => record

    event CredentialAnchored(bytes32 indexed referenceId, bytes32 recordHash, uint256 timestamp);

    constructor(address platformAdmin, address issuerRegistryAddress) {
        _grantRole(DEFAULT_ADMIN_ROLE, platformAdmin);
        _grantRole(PLATFORM_ADMIN_ROLE, platformAdmin);
        issuerRegistry = IssuerRegistry(issuerRegistryAddress);
    }

    /// @notice Anchors a credential commitment hash on-chain.
    /// @param recordHash Commitment hash of the credential's claims (never raw data).
    /// @param referenceId keccak256 of the off-chain credential UUID.
    function anchorRecord(bytes32 recordHash, bytes32 referenceId)
        external
        onlyRole(BACKEND_SERVICE_ROLE)
        whenNotPaused
        nonReentrant
    {
        require(recordHash != bytes32(0), "CredentialRegistry: empty hash");
        require(!_credentials[referenceId].exists, "CredentialRegistry: already anchored");

        _credentials[referenceId] = CredentialRecord({
            recordHash: recordHash,
            issuerRef: bytes32(0), // set via anchorRecordWithIssuer for stricter binding
            anchoredAt: block.timestamp,
            exists: true
        });

        emit CredentialAnchored(referenceId, recordHash, block.timestamp);
    }

    /// @notice Stricter variant that also binds the anchoring issuer and
    ///         requires that issuer to be currently approved and unblocked.
    function anchorRecordWithIssuer(bytes32 recordHash, bytes32 referenceId, bytes32 issuerRef)
        external
        onlyRole(BACKEND_SERVICE_ROLE)
        whenNotPaused
        nonReentrant
    {
        require(recordHash != bytes32(0), "CredentialRegistry: empty hash");
        require(!_credentials[referenceId].exists, "CredentialRegistry: already anchored");
        require(issuerRegistry.isApprovedIssuer(issuerRef), "CredentialRegistry: issuer not approved");

        _credentials[referenceId] = CredentialRecord({
            recordHash: recordHash,
            issuerRef: issuerRef,
            anchoredAt: block.timestamp,
            exists: true
        });

        emit CredentialAnchored(referenceId, recordHash, block.timestamp);
    }

    function getRecord(bytes32 referenceId) external view returns (bytes32 recordHash, bool exists) {
        CredentialRecord storage record = _credentials[referenceId];
        return (record.recordHash, record.exists);
    }

    /// @notice Verifies that a freshly computed commitment matches the
    ///         anchored one — the core on-chain integrity check.
    function verifyIntegrity(bytes32 referenceId, bytes32 candidateHash) external view returns (bool) {
        CredentialRecord storage record = _credentials[referenceId];
        return record.exists && record.recordHash == candidateHash;
    }

    function pause() external onlyRole(PLATFORM_ADMIN_ROLE) {
        _pause();
    }

    function unpause() external onlyRole(PLATFORM_ADMIN_ROLE) {
        _unpause();
    }
}
