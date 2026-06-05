// SPDX-License-Identifier: MIT
pragma solidity ^0.8.28;

/**
 * @title DecisionAuditLog
 * @notice Immutable on-chain record of every AI-driven parameter update.
 *         Every decision is permanently stored — cannot be deleted or modified.
 */
contract DecisionAuditLog {
    struct Decision {
        bytes32 policyId;
        uint256 fromValue;
        uint256 toValue;
        bytes   agentSignature;
        address agent;
        uint256 timestamp;
        uint256 blockNumber;
    }

    Decision[] private _decisions;

    // Index: policyId → decision indices
    mapping(bytes32 => uint256[]) private _policyDecisions;

    // Only authorized contracts (LivingBase implementations) can log
    mapping(address => bool) public authorizedLoggers;
    address public owner;

    event DecisionLogged(
        uint256 indexed decisionId,
        bytes32 indexed policyId,
        uint256 fromValue,
        uint256 toValue,
        address indexed agent,
        uint256 timestamp
    );

    error NotAuthorized();

    constructor() {
        owner = msg.sender;
    }

    modifier onlyAuthorized() {
        if (msg.sender != owner && !authorizedLoggers[msg.sender])
            revert NotAuthorized();
        _;
    }

    function authorizeLogger(address logger) external {
        require(msg.sender == owner, "Not owner");
        authorizedLoggers[logger] = true;
    }

    /**
     * @notice Log a new AI decision. Called by LivingBase modifier after execution.
     */
    function log(
        bytes32 policyId,
        uint256 fromValue,
        uint256 toValue,
        bytes calldata agentSignature
    ) external onlyAuthorized returns (uint256 decisionId) {
        decisionId = _decisions.length;

        _decisions.push(Decision({
            policyId:       policyId,
            fromValue:      fromValue,
            toValue:        toValue,
            agentSignature: agentSignature,
            agent:          tx.origin,
            timestamp:      block.timestamp,
            blockNumber:    block.number
        }));

        _policyDecisions[policyId].push(decisionId);

        emit DecisionLogged(decisionId, policyId, fromValue, toValue, tx.origin, block.timestamp);
    }

    // ─── Read ─────────────────────────────────────────────────────────────────

    function getDecision(uint256 id) external view returns (Decision memory) {
        return _decisions[id];
    }

    function getDecisionsByPolicy(bytes32 policyId)
        external view returns (uint256[] memory)
    {
        return _policyDecisions[policyId];
    }

    function totalDecisions() external view returns (uint256) {
        return _decisions.length;
    }

    function getLatestDecisions(uint256 count)
        external view returns (Decision[] memory)
    {
        uint256 total = _decisions.length;
        if (count > total) count = total;

        Decision[] memory result = new Decision[](count);
        for (uint256 i = 0; i < count; i++) {
            result[i] = _decisions[total - count + i];
        }
        return result;
    }
}
