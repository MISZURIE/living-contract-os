"""
Price feed module — fetches ETH/USD from CoinGecko (free tier) and CoinMarketCap.
In production, replace primary source with Chainlink OCR on-chain feed.
"""
import asyncio
import time
from dataclasses import dataclass
from typing import Optional

import httpx
import structlog

logger = structlog.get_logger(__name__)


@dataclass
class PriceData:
    symbol: str
    price_usd: float
    source: str
    timestamp: float
    volatility_24h: Optional[float] = None  # % change 24h as decimal (0.08 = 8%)


class PriceFeedAggregator:
    """
    Aggregates price data from multiple sources.
    Returns consensus price + quality score.
    """

    SOURCES = [
        "https://api.coingecko.com/api/v3/simple/price?ids=ethereum&vs_currencies=usd&include_24hr_change=true",
        "https://api.binance.com/api/v3/ticker/24hr?symbol=ETHUSDT",
    ]

    def __init__(self, timeout: float = 5.0):
        self.timeout = timeout
        self._cache: dict[str, PriceData] = {}
        self._cache_ttl = 30  # seconds

    async def get_eth_price(self) -> tuple[PriceData, float]:
        """
        Returns (price_data, quality_score).
        quality_score: 0.0–1.0. Below 0.90 = reject in pipeline.
        """
        results: list[PriceData] = []

        async with httpx.AsyncClient(timeout=self.timeout) as client:
            tasks = [
                self._fetch_coingecko(client),
                self._fetch_binance(client),
            ]
            raw = await asyncio.gather(*tasks, return_exceptions=True)

        for r in raw:
            if isinstance(r, PriceData):
                results.append(r)

        if not results:
            logger.error("all_price_sources_failed")
            return PriceData("ETH", 0.0, "none", time.time()), 0.0

        prices = [r.price_usd for r in results]
        avg_price = sum(prices) / len(prices)
        # Quality: penalize if sources disagree > 0.5%
        max_deviation = max(abs(p - avg_price) / avg_price for p in prices) if len(prices) > 1 else 0.0
        quality = max(0.0, 1.0 - (max_deviation * 100))  # 1% deviation → 0.0 quality

        volatility = results[0].volatility_24h

        consensus = PriceData(
            symbol="ETH",
            price_usd=round(avg_price, 2),
            source=f"consensus({len(results)} sources)",
            timestamp=time.time(),
            volatility_24h=volatility,
        )

        logger.info("price_fetched", price=consensus.price_usd, quality=round(quality, 3), sources=len(results))
        return consensus, round(quality, 3)

    async def _fetch_coingecko(self, client: httpx.AsyncClient) -> PriceData:
        resp = await client.get(self.SOURCES[0])
        resp.raise_for_status()
        data = resp.json()
        eth = data["ethereum"]
        return PriceData(
            symbol="ETH",
            price_usd=float(eth["usd"]),
            source="coingecko",
            timestamp=time.time(),
            volatility_24h=abs(float(eth.get("usd_24h_change", 0.0))) / 100,
        )

    async def _fetch_binance(self, client: httpx.AsyncClient) -> PriceData:
        resp = await client.get(self.SOURCES[1])
        resp.raise_for_status()
        data = resp.json()
        return PriceData(
            symbol="ETH",
            price_usd=float(data["lastPrice"]),
            source="binance",
            timestamp=time.time(),
            volatility_24h=abs(float(data.get("priceChangePercent", 0.0))) / 100,
        )
