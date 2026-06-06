"""
ProposalAgent — Uses LLM (GPT-4o) to reason about parameter updates.
Receives validated market data + policy context → produces a structured proposal.
"""
from __future__ import annotations

import json
from dataclasses import dataclass
from typing import Optional

import structlog
from openai import AsyncOpenAI

from ..feeds.price_feed import PriceData

GROQ_BASE_URL = "https://api.groq.com/openai/v1"

logger = structlog.get_logger(__name__)


@dataclass
class PolicyContext:
    policy_id: str
    name: str
    current: int
    min_value: int
    max_value: int
    max_delta_per_epoch: int


@dataclass
class Proposal:
    proposed_value: int
    confidence: float        # 0.0–1.0
    reasoning: str
    within_boundary: bool


SYSTEM_PROMPT = """You are a DeFi protocol parameter management AI.
Your job is to propose smart contract parameter updates based on market conditions.

RULES:
1. You MUST stay within the provided [min, max] boundary.
2. You MUST NOT change more than max_delta_per_epoch in one update.
3. Your proposed_value must be an integer.
4. Your confidence must reflect how certain you are (0.0–1.0).
5. Be conservative — small adjustments are preferred over large ones.
6. Respond ONLY with valid JSON matching the schema provided.
"""

PROPOSAL_SCHEMA = {
    "type": "object",
    "properties": {
        "proposed_value": {"type": "integer"},
        "confidence":     {"type": "number", "minimum": 0, "maximum": 1},
        "reasoning":      {"type": "string"},
    },
    "required": ["proposed_value", "confidence", "reasoning"],
}


class ProposalAgent:
    def __init__(self, api_key: str, model: str = "llama-3.3-70b-versatile"):
        self.client = AsyncOpenAI(
            api_key=api_key,
            base_url=GROQ_BASE_URL,
        )
        self.model  = model

    async def propose(
        self,
        price_data: PriceData,
        policy: PolicyContext,
        data_quality: float,
    ) -> Optional[Proposal]:
        """Generate a parameter update proposal based on market data and policy context."""

        user_message = f"""
Market Data:
- ETH/USD price: ${price_data.price_usd:,.2f}
- 24h volatility: {(price_data.volatility_24h or 0) * 100:.2f}%
- Data quality score: {data_quality:.2f}
- Timestamp: {price_data.timestamp:.0f}

Policy: {policy.name}
- Current value: {policy.current} ({policy.current / 100:.2f}%)
- Boundary: [{policy.min_value}, {policy.max_value}] ({policy.min_value/100:.2f}% – {policy.max_value/100:.2f}%)
- Max change per epoch: ±{policy.max_delta_per_epoch} ({policy.max_delta_per_epoch/100:.2f}%)

Task: Propose a new value for this parameter. Consider market volatility.
Higher volatility → consider adjusting fee upward (within boundary).
Low volatility → consider moving fee back toward neutral (500).

Respond with JSON only:
{{"proposed_value": <integer>, "confidence": <0.0-1.0>, "reasoning": "<concise explanation>"}}
"""
        try:
            response = await self.client.chat.completions.create(
                model=self.model,
                messages=[
                    {"role": "system", "content": SYSTEM_PROMPT},
                    {"role": "user",   "content": user_message},
                ],
                response_format={"type": "json_object"},
                temperature=0.2,  # low temp = deterministic, conservative
                max_tokens=256,
            )

            raw = response.choices[0].message.content
            data = json.loads(raw)

            proposed = int(data["proposed_value"])
            within_boundary = policy.min_value <= proposed <= policy.max_value
            # Clamp delta
            delta = abs(proposed - policy.current)
            if delta > policy.max_delta_per_epoch:
                # Clamp to max delta
                direction = 1 if proposed > policy.current else -1
                proposed = policy.current + (direction * policy.max_delta_per_epoch)
                within_boundary = policy.min_value <= proposed <= policy.max_value

            proposal = Proposal(
                proposed_value=proposed,
                confidence=float(data["confidence"]),
                reasoning=str(data["reasoning"])[:500],  # truncate for on-chain
                within_boundary=within_boundary,
            )

            logger.info(
                "proposal_generated",
                proposed=proposal.proposed_value,
                confidence=proposal.confidence,
                within_boundary=proposal.within_boundary,
            )
            return proposal

        except Exception as e:
            logger.error("proposal_failed", error=str(e))
            return None
