// SPDX-License-Identifier: MIT
pragma solidity ^0.8.24;

import "@openzeppelin/contracts/access/AccessControl.sol";
import "@openzeppelin/contracts/utils/Pausable.sol";
import "@openzeppelin/contracts/utils/ReentrancyGuard.sol";

/// @title RevocationRegistry
/// @notice Anchors credential revocation events on-chain so any verifier
///         can independently confirm a credential's current status
///         without trusting the issuer's centralized database. Stores
///         only reference-id => revoked boolean and a hash of the
///         revocation record — never PII or revocation reasons in plaintext.
contract RevocationRegistry is AccessControl, Pausable, ReentrancyGuard {
    bytes32 public constant BACKEND_SERVICE_ROLE = keccak256("BACKEND_SERVICE_ROLE");
    bytes32 public constant PLATFORM_ADMIN_ROLE = keccak256("PLATFORM_ADMIN_ROLE");

    struct RevocationRecord {
        bytes32 recordHash;
        uint256 revokedAt;
        bool revoked;
    }

    mapping(bytes32 => RevocationRecord) private _revocations; // referenceId => record

    event CredentialRevoked(bytes32 indexed referenceId, bytes32 recordHash, uint256 timestamp);
    event RevocationReversed(bytes32 indexed referenceId, uint256 timestamp);

    constructor(address platformAdmin) {
        _grantRole(DEFAULT_ADMIN_ROLE, platformAdmin);
        _grantRole(PLATFORM_ADMIN_ROLE, platformAdmin);
    }

    /// @notice Anchors a credential revocation. Idempotent per referenceId.
    function anchorRecord(bytes32 recordHash, bytes32 referenceId)
        external
        onlyRole(BACKEND_SERVICE_ROLE)
        whenNotPaused
        nonReentrant
    {
        require(recordHash != bytes32(0), "RevocationRegistry: empty hash");

        _revocations[referenceId] = RevocationRecord({
            recordHash: recordHash,
            revokedAt: block.timestamp,
            revoked: true
        });

        emit CredentialRevoked(referenceId, recordHash, block.timestamp);
    }

    /// @notice Admin-only emergency reversal (e.g. revocation issued in error).
    ///         Reversal itself is transparently logged via the emitted event.
    function reverseRevocation(bytes32 referenceId) external onlyRole(PLATFORM_ADMIN_ROLE) whenNotPaused {
        require(_revocations[referenceId].revoked, "RevocationRegistry: not revoked");
        _revocations[referenceId].revoked = false;
        emit RevocationReversed(referenceId, block.timestamp);
    }

    function isRevoked(bytes32 referenceId) external view returns (bool) {
        return _revocations[referenceId].revoked;
    }

    function getRecord(bytes32 referenceId) external view returns (bytes32 recordHash, bool exists) {
        RevocationRecord storage record = _revocations[referenceId];
        return (record.recordHash, record.revokedAt != 0);
    }

    function pause() external onlyRole(PLATFORM_ADMIN_ROLE) {
        _pause();
    }

    function unpause() external onlyRole(PLATFORM_ADMIN_ROLE) {
        _unpause();
    }
}
