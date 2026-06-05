// SPDX-License-Identifier: MIT
pragma solidity ^0.8.28;

import "@openzeppelin/contracts/access/Ownable.sol";

/**
 * @title PolicyRegistry
 * @notice Stores and manages parameter boundaries that AI agents must respect.
 *         Only the contract owner can define or modify boundaries.
 */
contract PolicyRegistry is Ownable {
    struct PolicyBoundary {
        uint256 current;           // current parameter value
        uint256 minValue;          // floor — AI cannot go below
        uint256 maxValue;          // ceiling — AI cannot go above
        uint256 maxDeltaPerEpoch;  // max change per epoch
        uint256 epochLength;       // epoch in seconds
        uint256 lastEpochTime;     // last epoch start timestamp
        bool    requiresDAOIfBoundary; // trigger DAO vote if AI hits boundary
        bytes32 policyId;          // unique identifier
        string  name;              // human-readable label
    }

    mapping(bytes32 => PolicyBoundary) private _policies;
    bytes32[] private _policyIds;

    // ─── Roles ───────────────────────────────────────────────────────────────
    mapping(address => bool) public authorizedUpdaters;

    // ─── Events ──────────────────────────────────────────────────────────────
    event PolicyCreated(bytes32 indexed policyId, string name, uint256 min, uint256 max);
    event PolicyUpdated(bytes32 indexed policyId, uint256 newCurrent);
    event BoundaryModified(bytes32 indexed policyId, uint256 newMin, uint256 newMax);

    // ─── Errors ──────────────────────────────────────────────────────────────
    error PolicyNotFound(bytes32 policyId);
    error PolicyAlreadyExists(bytes32 policyId);
    error NotAuthorized();

    constructor() Ownable(msg.sender) {}

    modifier onlyAuthorized() {
        if (msg.sender != owner() && !authorizedUpdaters[msg.sender])
            revert NotAuthorized();
        _;
    }

    // ─── Policy CRUD ─────────────────────────────────────────────────────────

    function createPolicy(
        bytes32 policyId,
        string calldata name,
        uint256 initialValue,
        uint256 minValue,
        uint256 maxValue,
        uint256 maxDeltaPerEpoch,
        uint256 epochLength,
        bool requiresDAOIfBoundary
    ) external onlyOwner {
        if (_policies[policyId].policyId == policyId && _policies[policyId].maxValue > 0)
            revert PolicyAlreadyExists(policyId);

        _policies[policyId] = PolicyBoundary({
            current:               initialValue,
            minValue:              minValue,
            maxValue:              maxValue,
            maxDeltaPerEpoch:      maxDeltaPerEpoch,
            epochLength:           epochLength,
            lastEpochTime:         block.timestamp,
            requiresDAOIfBoundary: requiresDAOIfBoundary,
            policyId:              policyId,
            name:                  name
        });

        _policyIds.push(policyId);
        emit PolicyCreated(policyId, name, minValue, maxValue);
    }

    function getPolicy(bytes32 policyId) external view returns (PolicyBoundary memory) {
        if (_policies[policyId].maxValue == 0 && _policies[policyId].minValue == 0)
            revert PolicyNotFound(policyId);
        return _policies[policyId];
    }

    function updateCurrent(bytes32 policyId, uint256 newValue) external onlyAuthorized {
        _policies[policyId].current = newValue;
        emit PolicyUpdated(policyId, newValue);
    }

    function modifyBoundary(
        bytes32 policyId,
        uint256 newMin,
        uint256 newMax
    ) external onlyOwner {
        _policies[policyId].minValue = newMin;
        _policies[policyId].maxValue = newMax;
        emit BoundaryModified(policyId, newMin, newMax);
    }

    function authorizeUpdater(address updater) external onlyOwner {
        authorizedUpdaters[updater] = true;
    }

    function getAllPolicyIds() external view returns (bytes32[] memory) {
        return _policyIds;
    }
}
