"""
ContractExecutionAgent — Submits transactions to the LivingContract on-chain.
Uses the agent's private key (session key pattern via EIP-7702 in prod).
"""
from __future__ import annotations

import json
import time
from dataclasses import dataclass
from pathlib import Path
from typing import Optional

import structlog
from web3 import Web3
from web3.middleware import ExtraDataToPOAMiddleware

logger = structlog.get_logger(__name__)

# ABI — minimal interface for DynamicFeeContract
DYNAMIC_FEE_ABI = json.loads("""
[
  {
    "name": "updateFee",
    "type": "function",
    "inputs": [
      {"name": "newFeeBps",  "type": "uint256"},
      {"name": "zkProof",    "type": "bytes"},
      {"name": "agentSig",   "type": "bytes"},
      {"name": "reasoning",  "type": "string"}
    ],
    "outputs": [],
    "stateMutability": "nonpayable"
  },
  {
    "name": "getFee",
    "type": "function",
    "inputs": [],
    "outputs": [{"name": "", "type": "uint256"}],
    "stateMutability": "view"
  }
]
""")


@dataclass
class TxResult:
    tx_hash: str
    block_number: int
    gas_used: int
    success: bool
    error: Optional[str] = None


class ContractExecutor:
    def __init__(
        self,
        rpc_url: str,
        private_key: str,
        contract_address: str,
    ):
        self.w3 = Web3(Web3.HTTPProvider(rpc_url))
        # Inject POA middleware for Sepolia
        self.w3.middleware_onion.inject(ExtraDataToPOAMiddleware, layer=0)

        self.account  = self.w3.eth.account.from_key(private_key)
        self.contract = self.w3.eth.contract(
            address=Web3.to_checksum_address(contract_address),
            abi=DYNAMIC_FEE_ABI,
        )

        logger.info("executor_initialized",
                    address=self.account.address,
                    contract=contract_address,
                    chain_id=self.w3.eth.chain_id)

    async def submit_fee_update(
        self,
        new_fee_bps: int,
        zk_proof: bytes,
        agent_sig: bytes,
        reasoning: str,
    ) -> TxResult:
        """Build, sign, and submit the updateFee transaction."""
        try:
            nonce   = self.w3.eth.get_transaction_count(self.account.address)
            gas_est = self.contract.functions.updateFee(
                new_fee_bps, zk_proof, agent_sig, reasoning
            ).estimate_gas({"from": self.account.address})

            tx = self.contract.functions.updateFee(
                new_fee_bps, zk_proof, agent_sig, reasoning
            ).build_transaction({
                "from":     self.account.address,
                "nonce":    nonce,
                "gas":      int(gas_est * 1.2),  # 20% buffer
                "maxFeePerGas":         self.w3.eth.gas_price * 2,
                "maxPriorityFeePerGas": Web3.to_wei(1, "gwei"),
                "chainId": self.w3.eth.chain_id,
            })

            signed  = self.w3.eth.account.sign_transaction(tx, self.account.key)
            tx_hash = self.w3.eth.send_raw_transaction(signed.raw_transaction)

            logger.info("tx_submitted", tx_hash=tx_hash.hex(), new_fee=new_fee_bps)

            receipt = self.w3.eth.wait_for_transaction_receipt(tx_hash, timeout=120)

            result = TxResult(
                tx_hash=tx_hash.hex(),
                block_number=receipt["blockNumber"],
                gas_used=receipt["gasUsed"],
                success=receipt["status"] == 1,
            )

            logger.info("tx_confirmed",
                        tx_hash=result.tx_hash,
                        block=result.block_number,
                        gas=result.gas_used,
                        success=result.success)
            return result

        except Exception as e:
            logger.error("tx_failed", error=str(e))
            return TxResult(tx_hash="", block_number=0, gas_used=0, success=False, error=str(e))

    def get_current_fee(self) -> int:
        return self.contract.functions.getFee().call()
