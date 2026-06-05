// SPDX-License-Identifier: MIT
pragma solidity ^0.8.28;

import "@openzeppelin/contracts-upgradeable/access/AccessControlUpgradeable.sol";
import "@openzeppelin/contracts-upgradeable/utils/PausableUpgradeable.sol";
import "@openzeppelin/contracts-upgradeable/proxy/utils/UUPSUpgradeable.sol";
import "@openzeppelin/contracts-upgradeable/proxy/utils/Initializable.sol";
import "./PolicyRegistry.sol";
import "./DecisionAuditLog.sol";
import "./MockZKVerifier.sol";
import "./CircuitBreaker.sol";

/**
 * @title LivingBase
 * @notice Abstract base contract for AI-governed self-evolving smart contracts.
 *         AI agents can update parameters within policy boundaries.
 *         Every decision is ZK-verified and immutably logged on-chain.
 */
abstract contract LivingBase is
    Initializable,
    AccessControlUpgradeable,
    PausableUpgradeable,
    UUPSUpgradeable
{
    // ─── Roles ───────────────────────────────────────────────────────────────
    bytes32 public constant AGENT_ROLE    = keccak256("AGENT_ROLE");
    bytes32 public constant UPGRADER_ROLE = keccak256("UPGRADER_ROLE");

    // ─── Sub-contracts ───────────────────────────────────────────────────────
    PolicyRegistry   public policyRegistry;
    DecisionAuditLog public auditLog;
    MockZKVerifier   public zkVerifier;
    CircuitBreaker   public circuitBreaker;

    // ─── Events ──────────────────────────────────────────────────────────────
    event ParameterUpdated(
        bytes32 indexed policyId,
        uint256 oldValue,
        uint256 newValue,
        address indexed agent,
        uint256 timestamp
    );

    event GovernanceRequired(
        bytes32 indexed policyId,
        uint256 proposedValue,
        string  reason
    );

    // ─── Errors ──────────────────────────────────────────────────────────────
    error InvalidZKProof();
    error OutsidePolicyBoundary(uint256 value, uint256 min, uint256 max);
    error CircuitBreakerActive();
    error UnauthorizedAgent();

    // ─── Modifier ────────────────────────────────────────────────────────────
    modifier onlyWithinPolicy(
        bytes32 policyId,
        uint256 newValue,
        bytes calldata zkProof,
        bytes calldata agentSignature
    ) {
        if (circuitBreaker.isTripped()) revert CircuitBreakerActive();

        // Verify ZK proof (mock on testnet, real Groth16 on mainnet)
        bool valid = zkVerifier.verify(
            zkProof,
            abi.encode(newValue, policyId, block.timestamp)
        );
        if (!valid) revert InvalidZKProof();

        PolicyRegistry.PolicyBoundary memory policy = policyRegistry.getPolicy(policyId);

        if (newValue < policy.minValue || newValue > policy.maxValue) {
            if (policy.requiresDAOIfBoundary) {
                emit GovernanceRequired(policyId, newValue, "exceeds boundary");
                revert OutsidePolicyBoundary(newValue, policy.minValue, policy.maxValue);
            }
            revert OutsidePolicyBoundary(newValue, policy.minValue, policy.maxValue);
        }

        _;

        // Log the decision immutably after execution
        auditLog.log(policyId, policy.current, newValue, agentSignature);

        emit ParameterUpdated(policyId, policy.current, newValue, msg.sender, block.timestamp);

        policyRegistry.updateCurrent(policyId, newValue);
    }

    // ─── Init ─────────────────────────────────────────────────────────────────
    function __LivingBase_init(
        address _policyRegistry,
        address _auditLog,
        address _zkVerifier,
        address _circuitBreaker
    ) internal onlyInitializing {
        __AccessControl_init();
        __Pausable_init();

        _grantRole(DEFAULT_ADMIN_ROLE, msg.sender);
        _grantRole(UPGRADER_ROLE, msg.sender);

        policyRegistry  = PolicyRegistry(_policyRegistry);
        auditLog        = DecisionAuditLog(_auditLog);
        zkVerifier      = MockZKVerifier(_zkVerifier);
        circuitBreaker  = CircuitBreaker(_circuitBreaker);
    }

    // ─── Agent management ────────────────────────────────────────────────────
    function addAgent(address agent) external onlyRole(DEFAULT_ADMIN_ROLE) {
        _grantRole(AGENT_ROLE, agent);
    }

    function removeAgent(address agent) external onlyRole(DEFAULT_ADMIN_ROLE) {
        _revokeRole(AGENT_ROLE, agent);
    }

    // ─── Emergency controls ──────────────────────────────────────────────────
    function pause() external onlyRole(DEFAULT_ADMIN_ROLE) {
        _pause();
    }

    function unpause() external onlyRole(DEFAULT_ADMIN_ROLE) {
        _unpause();
    }

    // ─── UUPS ────────────────────────────────────────────────────────────────
    function _authorizeUpgrade(address) internal override onlyRole(UPGRADER_ROLE) {}
}
