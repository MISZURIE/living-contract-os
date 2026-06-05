// SPDX-License-Identifier: MIT
pragma solidity ^0.8.28;

import "forge-std/Test.sol";
import "../src/PolicyRegistry.sol";
import "../src/DecisionAuditLog.sol";
import "../src/MockZKVerifier.sol";
import "../src/CircuitBreaker.sol";
import "../src/DynamicFeeContract.sol";
import "@openzeppelin/contracts/proxy/ERC1967/ERC1967Proxy.sol";

contract DynamicFeeContractTest is Test {
    PolicyRegistry   registry;
    DecisionAuditLog auditLog;
    MockZKVerifier   zkVerifier;
    CircuitBreaker   circuitBreaker;
    DynamicFeeContract feeContract;

    uint256 agentPk    = 0xA11CE;
    address agentAddr  = vm.addr(0xA11CE);
    address deployer   = address(this);

    bytes32 constant FEE_POLICY = keccak256("dynamic.fee.v1");

    function setUp() public {
        registry      = new PolicyRegistry();
        auditLog      = new DecisionAuditLog();
        zkVerifier    = new MockZKVerifier(true);
        
        address[5] memory gs = [deployer, deployer, deployer, deployer, deployer];
        circuitBreaker = new CircuitBreaker(gs);

        DynamicFeeContract impl = new DynamicFeeContract();
        bytes memory data = abi.encodeCall(
            DynamicFeeContract.initialize,
            (address(registry), address(auditLog), address(zkVerifier), address(circuitBreaker), 500)
        );
        ERC1967Proxy proxy = new ERC1967Proxy(address(impl), data);
        feeContract = DynamicFeeContract(address(proxy));

        registry.authorizeUpdater(address(feeContract));
        auditLog.authorizeLogger(address(feeContract));
        zkVerifier.addProver(agentAddr);
        feeContract.addAgent(agentAddr);

        registry.createPolicy(FEE_POLICY, "Dynamic Fee", 500, 425, 575, 75, 86400, false);
    }

    function _makeProof(uint256 newValue, bytes32 policyId) internal view returns (bytes memory) {
        bytes memory input = abi.encode(newValue, policyId, block.timestamp);
        bytes32 msgHash = keccak256(input);
        bytes32 ethHash = keccak256(abi.encodePacked("\x19Ethereum Signed Message:\n32", msgHash));
        (uint8 v, bytes32 r, bytes32 s) = vm.sign(agentPk, ethHash);
        return abi.encodePacked(r, s, v);
    }

    function test_InitialFee() public view {
        assertEq(feeContract.getFee(), 500);
    }

    function test_AgentCanUpdateFeeWithinBoundary() public {
        bytes memory proof = _makeProof(520, FEE_POLICY);
        bytes memory sig   = _makeProof(520, FEE_POLICY); // reuse for agentSig in mock

        vm.prank(agentAddr);
        feeContract.updateFee(520, proof, sig, "volatility spike");

        assertEq(feeContract.getFee(), 520);
        assertEq(auditLog.totalDecisions(), 1);
    }

    function test_RevertIfOutsideBoundary() public {
        bytes memory proof = _makeProof(700, FEE_POLICY);
        bytes memory sig   = _makeProof(700, FEE_POLICY);

        vm.prank(agentAddr);
        vm.expectRevert();
        feeContract.updateFee(700, proof, sig, "way too high");
    }

    function test_RevertIfNotAgent() public {
        bytes memory proof = _makeProof(510, FEE_POLICY);

        vm.prank(address(0xBEEF));
        vm.expectRevert();
        feeContract.updateFee(510, proof, proof, "unauthorized");
    }

    function test_CircuitBreakerStopsUpdates() public {
        circuitBreaker.trip("market crisis");

        bytes memory proof = _makeProof(510, FEE_POLICY);
        vm.prank(agentAddr);
        vm.expectRevert(LivingBase.CircuitBreakerActive.selector);
        feeContract.updateFee(510, proof, proof, "should fail");
    }

    function test_AuditLogRecordsDecision() public {
        bytes memory proof = _makeProof(530, FEE_POLICY);

        vm.prank(agentAddr);
        feeContract.updateFee(530, proof, proof, "test");

        DecisionAuditLog.Decision[] memory decisions = auditLog.getLatestDecisions(1);
        assertEq(decisions[0].fromValue, 500);
        assertEq(decisions[0].toValue,   530);
        assertEq(decisions[0].policyId,  FEE_POLICY);
    }
}
