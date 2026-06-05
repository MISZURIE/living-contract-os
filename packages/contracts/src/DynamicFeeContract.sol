// SPDX-License-Identifier: MIT
pragma solidity ^0.8.28;

import "./LivingBase.sol";

/**
 * @title DynamicFeeContract
 * @notice Concrete example: DeFi protocol fee that AI adjusts based on market volatility.
 *         Inherits LivingBase — AI can only change fee within the policy boundary.
 *
 *         Policy: fee = 500 (5.00%), boundary [425, 575], ±15% per epoch (24h)
 */
contract DynamicFeeContract is LivingBase {
    bytes32 public constant FEE_POLICY_ID = keccak256("dynamic.fee.v1");

    // Current fee in basis points (500 = 5.00%)
    uint256 public currentFeeBps;

    event FeeUpdated(uint256 oldFee, uint256 newFee, string reasoning);

    function initialize(
        address _policyRegistry,
        address _auditLog,
        address _zkVerifier,
        address _circuitBreaker,
        uint256 initialFeeBps
    ) external initializer {
        __LivingBase_init(_policyRegistry, _auditLog, _zkVerifier, _circuitBreaker);
        currentFeeBps = initialFeeBps;
    }

    /**
     * @notice AI agent calls this to update the fee within policy bounds.
     * @param newFeeBps    Proposed fee in basis points
     * @param zkProof      ZK proof (mock: ECDSA signature on testnet)
     * @param agentSig     Agent's identity signature
     * @param reasoning    Off-chain reasoning string (stored in event, not on-chain storage)
     */
    function updateFee(
        uint256 newFeeBps,
        bytes calldata zkProof,
        bytes calldata agentSig,
        string calldata reasoning
    )
        external
        onlyRole(AGENT_ROLE)
        whenNotPaused
        onlyWithinPolicy(FEE_POLICY_ID, newFeeBps, zkProof, agentSig)
    {
        uint256 old = currentFeeBps;
        currentFeeBps = newFeeBps;
        emit FeeUpdated(old, newFeeBps, reasoning);
    }

    /**
     * @notice Anyone can read the current fee (for integrations)
     */
    function getFee() external view returns (uint256) {
        return currentFeeBps;
    }

    /**
     * @notice Get fee as a fraction (for UI display: 500 → "5.00%")
     */
    function getFeePercent() external view returns (uint256 whole, uint256 decimal) {
        whole   = currentFeeBps / 100;
        decimal = currentFeeBps % 100;
    }
}
