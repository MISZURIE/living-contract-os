// SPDX-License-Identifier: MIT
pragma solidity ^0.8.28;

import "forge-std/Script.sol";
import "../src/PolicyRegistry.sol";
import "../src/DecisionAuditLog.sol";
import "../src/MockZKVerifier.sol";
import "../src/CircuitBreaker.sol";
import "../src/DynamicFeeContract.sol";
import "@openzeppelin/contracts/proxy/ERC1967/ERC1967Proxy.sol";

contract Deploy is Script {
    function run() external {
        uint256 deployerPk = vm.envUint("DEPLOYER_PRIVATE_KEY");
        address deployer   = vm.addr(deployerPk);
        address agentAddr  = vm.envAddress("AGENT_ADDRESS");

        vm.startBroadcast(deployerPk);

        // 1. Deploy infrastructure contracts
        PolicyRegistry registry = new PolicyRegistry();
        DecisionAuditLog auditLog = new DecisionAuditLog();
        MockZKVerifier zkVerifier = new MockZKVerifier(true); // mock mode = true on testnet
        
        address[5] memory guardians = [
            deployer, deployer, deployer, deployer, deployer // use real multisig in prod
        ];
        CircuitBreaker circuitBreaker = new CircuitBreaker(guardians);

        // 2. Deploy DynamicFeeContract via UUPS proxy
        DynamicFeeContract impl = new DynamicFeeContract();
        bytes memory initData = abi.encodeCall(
            DynamicFeeContract.initialize,
            (address(registry), address(auditLog), address(zkVerifier), address(circuitBreaker), 500)
        );
        ERC1967Proxy proxy = new ERC1967Proxy(address(impl), initData);
        DynamicFeeContract feeContract = DynamicFeeContract(address(proxy));

        // 3. Wire permissions
        registry.authorizeUpdater(address(feeContract));
        auditLog.authorizeLogger(address(feeContract));
        zkVerifier.addProver(agentAddr);   // agent can sign proofs
        feeContract.addAgent(agentAddr);   // agent can call updateFee

        // 4. Create the fee policy boundary
        registry.createPolicy(
            keccak256("dynamic.fee.v1"),
            "Dynamic Protocol Fee",
            500,   // initial: 5.00%
            425,   // min: 4.25%
            575,   // max: 5.75%
            75,    // maxDeltaPerEpoch: ±0.75%
            86400, // epochLength: 24 hours
            true   // requiresDAOIfBoundary
        );

        vm.stopBroadcast();

        // Log deployed addresses
        console.log("=== LivingContract OS Deployment ===");
        console.log("PolicyRegistry:    ", address(registry));
        console.log("DecisionAuditLog:  ", address(auditLog));
        console.log("MockZKVerifier:    ", address(zkVerifier));
        console.log("CircuitBreaker:    ", address(circuitBreaker));
        console.log("DynamicFeeContract:", address(proxy));
        console.log("Agent address:     ", agentAddr);
    }
}
