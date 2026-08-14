// SPDX-License-Identifier: MIT
pragma solidity ^0.8.24;

import "@openzeppelin/contracts/access/AccessControl.sol";
import "@openzeppelin/contracts/utils/Pausable.sol";

/// @title IssuerRegistry
/// @notice Tracks which organizations are approved to issue verifiable
///         credentials on the platform. Stores ONLY a hashed reference to
///         each issuer's off-chain profile and an approval/blocked boolean
///         — no organization names, contact details, or other PII.
contract IssuerRegistry is AccessControl, Pausable {
    bytes32 public constant PLATFORM_ADMIN_ROLE = keccak256("PLATFORM_ADMIN_ROLE");
    bytes32 public constant BACKEND_SERVICE_ROLE = keccak256("BACKEND_SERVICE_ROLE");

    struct IssuerRecord {
        bytes32 recordHash; // sha256 hash of the off-chain issuer profile commitment
        bool approved;
        bool blocked;
        uint256 registeredAt;
    }

    mapping(bytes32 => IssuerRecord) private _issuers; // referenceId => record

    event IssuerRegistered(bytes32 indexed referenceId, bytes32 recordHash, uint256 timestamp);
    event IssuerApproved(bytes32 indexed referenceId, uint256 timestamp);
    event IssuerBlocked(bytes32 indexed referenceId, uint256 timestamp);
    event IssuerUnblocked(bytes32 indexed referenceId, uint256 timestamp);

    constructor(address platformAdmin) {
        _grantRole(DEFAULT_ADMIN_ROLE, platformAdmin);
        _grantRole(PLATFORM_ADMIN_ROLE, platformAdmin);
    }

    /// @notice Registers (or re-anchors) an issuer's off-chain profile hash.
    /// @dev Called by the backend service role only — never accepts raw PII.
    function anchorRecord(bytes32 recordHash, bytes32 referenceId)
        external
        onlyRole(BACKEND_SERVICE_ROLE)
        whenNotPaused
    {
        require(recordHash != bytes32(0), "IssuerRegistry: empty hash");
        IssuerRecord storage record = _issuers[referenceId];
        record.recordHash = recordHash;
        if (record.registeredAt == 0) {
            record.registeredAt = block.timestamp;
        }
        emit IssuerRegistered(referenceId, recordHash, block.timestamp);
    }

    function approveIssuer(bytes32 referenceId) external onlyRole(PLATFORM_ADMIN_ROLE) whenNotPaused {
        require(_issuers[referenceId].registeredAt != 0, "IssuerRegistry: unknown issuer");
        _issuers[referenceId].approved = true;
        _issuers[referenceId].blocked = false;
        emit IssuerApproved(referenceId, block.timestamp);
    }

    function blockIssuer(bytes32 referenceId) external onlyRole(PLATFORM_ADMIN_ROLE) whenNotPaused {
        require(_issuers[referenceId].registeredAt != 0, "IssuerRegistry: unknown issuer");
        _issuers[referenceId].blocked = true;
        emit IssuerBlocked(referenceId, block.timestamp);
    }

    function unblockIssuer(bytes32 referenceId) external onlyRole(PLATFORM_ADMIN_ROLE) whenNotPaused {
        require(_issuers[referenceId].registeredAt != 0, "IssuerRegistry: unknown issuer");
        _issuers[referenceId].blocked = false;
        emit IssuerUnblocked(referenceId, block.timestamp);
    }

    function isApprovedIssuer(bytes32 referenceId) external view returns (bool) {
        IssuerRecord storage record = _issuers[referenceId];
        return record.approved && !record.blocked;
    }

    function getRecord(bytes32 referenceId) external view returns (bytes32 recordHash, bool exists) {
        IssuerRecord storage record = _issuers[referenceId];
        return (record.recordHash, record.registeredAt != 0);
    }

    function pause() external onlyRole(PLATFORM_ADMIN_ROLE) {
        _pause();
    }

    function unpause() external onlyRole(PLATFORM_ADMIN_ROLE) {
        _unpause();
    }
}
