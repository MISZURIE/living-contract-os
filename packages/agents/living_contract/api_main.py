"""
LivingContract OS — REST API
FastAPI backend exposing contract state, decision history, and manual trigger.
"""
from __future__ import annotations

import json
import os
from contextlib import asynccontextmanager
from typing import Any

import redis.asyncio as aioredis
import structlog
from fastapi import FastAPI, HTTPException, BackgroundTasks
from fastapi.middleware.cors import CORSMiddleware
from pydantic import BaseModel

logger = structlog.get_logger(__name__)

# ── Redis connection ──────────────────────────────────────────────────────────
redis_client: aioredis.Redis | None = None

@asynccontextmanager
async def lifespan(app: FastAPI):
    global redis_client
    redis_url = os.getenv("REDIS_URL", "redis://redis:6379/0")
    redis_client = await aioredis.from_url(redis_url, decode_responses=True)
    logger.info("api_started", redis=redis_url)
    yield
    if redis_client:
        await redis_client.aclose()

# ── App ───────────────────────────────────────────────────────────────────────
app = FastAPI(
    title="LivingContract OS API",
    description="AI-Governed Self-Evolving Smart Contract Engine",
    version="0.1.0",
    lifespan=lifespan,
)

app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],  # restrict in prod
    allow_methods=["*"],
    allow_headers=["*"],
)

# ── Models ────────────────────────────────────────────────────────────────────
class ManualTriggerRequest(BaseModel):
    reason: str = "manual_trigger"

class HealthResponse(BaseModel):
    status: str
    version: str

# ── Routes ────────────────────────────────────────────────────────────────────

@app.get("/health", response_model=HealthResponse)
async def health():
    return {"status": "ok", "version": "0.1.0"}


@app.get("/v1/contracts/latest-run")
async def get_latest_run() -> dict[str, Any]:
    """Return the most recent agent pipeline result."""
    if not redis_client:
        raise HTTPException(503, "Redis unavailable")
    raw = await redis_client.get("latest_run")
    if not raw:
        return {"status": "no_runs_yet"}
    return json.loads(raw)


@app.get("/v1/contracts/history")
async def get_run_history(limit: int = 20) -> list[dict]:
    """Return the last N pipeline runs."""
    if not redis_client:
        raise HTTPException(503, "Redis unavailable")
    limit = min(limit, 100)
    items = await redis_client.lrange("run_history", 0, limit - 1)
    return [json.loads(i) for i in items]


@app.get("/v1/contracts/policy")
async def get_policy() -> dict[str, Any]:
    """Return the current policy boundary (static for MVP, dynamic in prod)."""
    return {
        "policy_id":     "dynamic.fee.v1",
        "name":          "Dynamic Protocol Fee",
        "min_value":     425,
        "max_value":     575,
        "max_delta":     75,
        "epoch_length":  86400,
        "description":   "AI-managed DeFi protocol fee in basis points. 500 = 5.00%",
    }


@app.post("/v1/contracts/trigger")
async def manual_trigger(
    body: ManualTriggerRequest,
    background_tasks: BackgroundTasks,
) -> dict[str, str]:
    """Manually trigger one pipeline cycle (for demo purposes)."""
    async def _run():
        try:
            # Import here to avoid circular imports at startup
            import sys
            sys.path.insert(0, "/app/agents")
            from living_contract.pipeline import AgentPipeline
            pipeline = AgentPipeline()
            await pipeline.setup()
            result = await pipeline.run_once()
            logger.info("manual_trigger_complete", **result)
        except Exception as e:
            logger.error("manual_trigger_failed", error=str(e))

    background_tasks.add_task(_run)
    return {"status": "triggered", "reason": body.reason}


@app.get("/v1/contracts/stats")
async def get_stats() -> dict[str, Any]:
    """Return aggregate stats for the dashboard."""
    if not redis_client:
        raise HTTPException(503, "Redis unavailable")

    history_raw = await redis_client.lrange("run_history", 0, 99)
    history = [json.loads(i) for i in history_raw]

    executed = [r for r in history if r.get("status") == "executed"]
    skipped  = [r for r in history if r.get("status") == "skipped"]

    avg_confidence = (
        sum(r.get("confidence", 0) for r in executed) / len(executed)
        if executed else 0
    )

    return {
        "total_runs":      len(history),
        "executed":        len(executed),
        "skipped":         len(skipped),
        "avg_confidence":  round(avg_confidence, 3),
        "latest_fee":      executed[-1]["new_fee"] if executed else 500,
        "latest_tx":       executed[-1]["tx_hash"] if executed else None,
    }
