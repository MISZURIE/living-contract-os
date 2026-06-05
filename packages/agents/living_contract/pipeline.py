"""
Main agent pipeline — orchestrates all 5 agents in sequence:
  PolicyMonitor → DataValidation → ProposalAgent → MockProver → ContractExecutor

Run with: python -m living_contract.pipeline
"""
from __future__ import annotations

import asyncio
import time

import redis.asyncio as aioredis
import structlog

from .agents.executor import ContractExecutor
from .agents.proposal_agent import PolicyContext, ProposalAgent
from .config import settings
from .feeds.price_feed import PriceFeedAggregator
from .provers.mock_prover import MockProver

logger = structlog.get_logger(__name__)

# Policy id — must match keccak256("dynamic.fee.v1") deployed on-chain
FEE_POLICY_ID = bytes.fromhex(
    "a1b2c3d4e5f6a1b2c3d4e5f6a1b2c3d4e5f6a1b2c3d4e5f6a1b2c3d4e5f6a1b2"
)  # Replace with actual keccak256 output after deployment

POLICY_CONTEXT = PolicyContext(
    policy_id="dynamic.fee.v1",
    name="Dynamic Protocol Fee",
    current=500,
    min_value=425,
    max_value=575,
    max_delta_per_epoch=75,
)


class AgentPipeline:
    def __init__(self):
        self.price_feed  = PriceFeedAggregator()
        self.proposal    = ProposalAgent(settings.openai_api_key, settings.llm_model)
        self.prover      = MockProver(settings.agent_private_key)
        self.executor    = ContractExecutor(
            settings.rpc_url,
            settings.agent_private_key,
            settings.contract_address,
        )
        self.redis = None

    async def setup(self):
        self.redis = await aioredis.from_url(settings.redis_url, decode_responses=True)
        logger.info("pipeline_ready")

    async def run_once(self) -> dict:
        """Execute one full pipeline cycle. Returns result dict for API consumption."""
        run_id = f"run_{int(time.time())}"
        log = logger.bind(run_id=run_id)

        # ── Step 1: Fetch market data ─────────────────────────────────────────
        log.info("step_1_fetch_price")
        price_data, quality = await self.price_feed.get_eth_price()

        if quality < settings.min_data_quality_score:
            msg = f"Data quality {quality:.2f} below threshold {settings.min_data_quality_score}"
            log.warning("data_quality_too_low", quality=quality)
            return {"status": "skipped", "reason": msg, "run_id": run_id}

        # ── Step 2: Sync current on-chain value ───────────────────────────────
        log.info("step_2_read_contract")
        current_fee = self.executor.get_current_fee()
        POLICY_CONTEXT.current = current_fee

        # ── Step 3: LLM proposal ──────────────────────────────────────────────
        log.info("step_3_propose")
        proposal = await self.proposal.propose(price_data, POLICY_CONTEXT, quality)

        if not proposal:
            return {"status": "error", "reason": "proposal_agent_failed", "run_id": run_id}

        if not proposal.within_boundary:
            log.warning("proposal_outside_boundary", proposed=proposal.proposed_value)
            return {
                "status": "governance_required",
                "proposed": proposal.proposed_value,
                "reasoning": proposal.reasoning,
                "run_id": run_id,
            }

        if proposal.proposed_value == current_fee:
            log.info("no_change_needed", current=current_fee)
            return {"status": "no_change", "current": current_fee, "run_id": run_id}

        # ── Step 4: Generate proof ────────────────────────────────────────────
        log.info("step_4_generate_proof")
        proof_result = self.prover.generate_proof(
            new_value=proposal.proposed_value,
            policy_id=FEE_POLICY_ID,
        )

        # ── Step 5: Submit on-chain ───────────────────────────────────────────
        log.info("step_5_submit_tx")
        tx_result = await self.executor.submit_fee_update(
            new_fee_bps=proposal.proposed_value,
            zk_proof=proof_result.proof_bytes,
            agent_sig=proof_result.proof_bytes,  # same signer in mock mode
            reasoning=proposal.reasoning[:200],
        )

        result = {
            "status":       "executed" if tx_result.success else "failed",
            "run_id":       run_id,
            "tx_hash":      tx_result.tx_hash,
            "block":        tx_result.block_number,
            "old_fee":      current_fee,
            "new_fee":      proposal.proposed_value,
            "confidence":   proposal.confidence,
            "reasoning":    proposal.reasoning,
            "eth_price":    price_data.price_usd,
            "data_quality": quality,
            "proof_type":   proof_result.proof_type,
            "proof_ms":     proof_result.generation_time_ms,
        }

        # Cache in Redis for API reads
        if self.redis:
            import json
            await self.redis.set("latest_run", json.dumps(result), ex=3600)
            await self.redis.lpush("run_history", json.dumps(result))
            await self.redis.ltrim("run_history", 0, 99)  # keep last 100

        return result

    async def run_loop(self):
        """Continuous polling loop — runs every poll_interval_seconds."""
        await self.setup()
        logger.info("pipeline_loop_started", interval=settings.poll_interval_seconds)

        while True:
            try:
                result = await self.run_once()
                logger.info("pipeline_cycle_complete", **result)
            except Exception as e:
                logger.error("pipeline_error", error=str(e))

            await asyncio.sleep(settings.poll_interval_seconds)


async def main():
    pipeline = AgentPipeline()
    await pipeline.run_loop()


if __name__ == "__main__":
    asyncio.run(main())
