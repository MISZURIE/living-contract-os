"""
MockProver — Testnet proof generator.
Signs (newValue, policyId, timestamp) with the agent's private key.
On mainnet, replace with EZKL circuit prover.
"""
from __future__ import annotations

import time
from dataclasses import dataclass

import structlog
from eth_account import Account
from eth_account.messages import encode_defunct
from web3 import Web3

logger = structlog.get_logger(__name__)


@dataclass
class ProofResult:
    proof_bytes: bytes          # 65-byte ECDSA signature
    public_inputs: dict         # what was proven (for audit)
    proof_type: str             # "mock_ecdsa" | "ezkl_groth16" | "tee_attestation"
    generation_time_ms: float


class MockProver:
    """
    Generates mock ZK proofs using ECDSA signatures.
    The on-chain MockZKVerifier contract accepts this format.

    Production replacement: swap with EZKLProver that generates
    real Groth16 proofs from ONNX model using EZKL library.
    """

    def __init__(self, private_key: str):
        self.account = Account.from_key(private_key)
        logger.info("mock_prover_initialized", address=self.account.address)

    def generate_proof(
        self,
        new_value: int,
        policy_id: bytes,        # bytes32
        timestamp: int | None = None,
    ) -> ProofResult:
        """Generate a mock ZK proof for the given parameter update."""
        import time as _time

        start = _time.monotonic()
        ts = timestamp or int(time.time())

        # Match exactly what MockZKVerifier.sol does:
        # keccak256(abi.encode(newValue, policyId, timestamp))
        encoded = Web3.solidity_keccak(
            ["uint256", "bytes32", "uint256"],
            [new_value, policy_id, ts]
        )

        # eth_sign prefix
        message = encode_defunct(encoded)
        signed  = self.account.sign_message(message)

        # Pack as r + s + v (65 bytes) — matches Solidity _splitSignature
        proof_bytes = signed.r.to_bytes(32, "big") + \
                      signed.s.to_bytes(32, "big") + \
                      signed.v.to_bytes(1, "big")

        elapsed = (_time.monotonic() - start) * 1000

        logger.info(
            "proof_generated",
            type="mock_ecdsa",
            signer=self.account.address,
            new_value=new_value,
            generation_ms=round(elapsed, 2),
        )

        return ProofResult(
            proof_bytes=proof_bytes,
            public_inputs={
                "new_value":  new_value,
                "policy_id":  policy_id.hex(),
                "timestamp":  ts,
            },
            proof_type="mock_ecdsa",
            generation_time_ms=round(elapsed, 2),
        )
