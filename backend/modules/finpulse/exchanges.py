"""
CCXT exchange connector — async wrapper around the sync ccxt library.

Design choices:
- ccxt is synchronous; we run blocking calls in asyncio's default thread pool
  (run_in_executor) so the FastAPI event loop never blocks.
- PAXG trades against USDT on most CEXs; we map the ticker correctly.
- Binance is used by default.  No API key needed for public market data.
- Prices are persisted in market_prices (TimescaleDB hypertable).
- fetch_and_store_prices() is the single entry-point called by the scheduler.
"""

import asyncio
import logging
from datetime import datetime, timezone
from typing import Optional

import ccxt

from ...core.config import get_settings
from ...core.database import execute_many, fetch_all

logger = logging.getLogger(__name__)

# Canonical CCXT pairs for each PULSE asset
SYMBOLS: dict[str, str] = {
    "BTC": "BTC/USDT",
    "ETH": "ETH/USDT",
    "PAXG": "PAXG/USDT",
}


def _build_exchange() -> ccxt.Exchange:
    """
    Create a ccxt Exchange instance for public market data.
    No API key needed — fetch_ticker is a public endpoint on Binance.
    enableRateLimit lets ccxt self-throttle to avoid HTTP 429.
    """
    settings = get_settings()
    exchange_cls = getattr(ccxt, settings.exchange_id, None)
    if exchange_cls is None:
        raise ValueError(f"Unknown exchange: {settings.exchange_id}")

    exchange: ccxt.Exchange = exchange_cls({"enableRateLimit": True})  # type: ignore[call-arg]
    return exchange


# Module-level singleton — created once, reused across calls
_exchange: Optional[ccxt.Exchange] = None


def _get_exchange() -> ccxt.Exchange:
    global _exchange
    if _exchange is None:
        _exchange = _build_exchange()
    return _exchange


# ─── Public helpers ────────────────────────────────────────────────────────────

async def fetch_ticker(symbol_pair: str) -> dict:
    """
    Async wrapper: fetch a single ticker from the exchange.
    Runs ccxt's sync call in the thread pool executor.
    """
    loop = asyncio.get_running_loop()
    exchange = _get_exchange()
    ticker = await loop.run_in_executor(
        None, exchange.fetch_ticker, symbol_pair
    )
    return ticker


async def fetch_current_prices() -> dict[str, float | None]:
    """
    Fetch BTC, ETH and PAXG spot prices concurrently.
    Returns: {"BTC": 67000.0, "ETH": 3200.0, "PAXG": 2050.0}
    """
    async def _safe_fetch(asset: str, pair: str) -> tuple[str, float | None]:
        try:
            ticker = await fetch_ticker(pair)
            price = ticker.get("last") or ticker.get("close")
            if price is None:
                raise ValueError(f"Null price in ticker for {pair}")
            logger.debug(f"{asset} = {price:.2f} USDT")
            return asset, float(price)
        except Exception as exc:
            logger.warning(f"Failed to fetch {pair}: {exc}")
            return asset, None

    tasks = [_safe_fetch(asset, pair) for asset, pair in SYMBOLS.items()]
    results = await asyncio.gather(*tasks)
    return dict(results)


async def fetch_ohlcv(asset: str, timeframe: str = "1d", limit: int = 365) -> list[list]:
    """
    Fetch OHLCV candles — used by DCAEngine for backtesting.
    Returns list of [timestamp_ms, open, high, low, close, volume].
    """
    pair = SYMBOLS.get(asset.upper())
    if pair is None:
        raise ValueError(f"Unknown asset: {asset}")

    loop = asyncio.get_running_loop()
    exchange = _get_exchange()

    ohlcv = await loop.run_in_executor(
        None,
        lambda: exchange.fetch_ohlcv(pair, timeframe=timeframe, limit=limit),
    )
    return ohlcv  # type: ignore[return-value]


async def fetch_and_store_prices() -> dict[str, float | None]:
    """
    Main scheduler entry-point:
    1. Fetch prices from exchange
    2. Persist to market_prices (upsert)
    3. Broadcast via WebSocket
    Returns the price dict for immediate use.
    """
    prices = await fetch_current_prices()
    now = datetime.now(timezone.utc)

    # Build rows for executemany — only assets with valid prices
    rows: list[tuple] = [
        (now, asset, price)
        for asset, price in prices.items()
        if price is not None
    ]

    if rows:
        await execute_many(
            """
            INSERT INTO market_prices (time, symbol, price)
            VALUES ($1, $2, $3)
            ON CONFLICT (time, symbol) DO UPDATE
                SET price = EXCLUDED.price
            """,
            rows,
        )
        logger.info(
            "Stored prices: "
            + " | ".join(f"{a}={p:.2f}" for a, p in prices.items() if p)
        )
    else:
        logger.warning("No valid prices returned from exchange")

    # Broadcast to connected WebSocket clients
    try:
        from ...api.websocket import broadcast
        await broadcast({"event": "prices_updated", "data": prices})
    except Exception as e:
        logger.debug(f"WS broadcast skipped: {e}")

    return prices


async def get_latest_prices_from_db() -> dict[str, dict]:
    """
    Fetch the most recent price row for each asset from TimescaleDB.
    Returns: {"BTC": {"price": 67000.0, "time": "..."}, ...}
    """
    rows = await fetch_all("""
        SELECT DISTINCT ON (symbol)
            symbol, price, time
        FROM market_prices
        ORDER BY symbol, time DESC
    """)
    return {
        row["symbol"]: {
            "price": float(row["price"]),
            "time": row["time"].isoformat(),
        }
        for row in rows
    }
