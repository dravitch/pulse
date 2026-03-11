"""
Signal engine — MVP scope: Golden Cross + Rebalance alerts.

Golden Cross:  MA50 crosses above MA200  → BUY signal
Death Cross:   MA50 crosses below MA200  → SELL / caution signal
Rebalance:     any asset drifts > threshold from target allocation
"""

import json
import logging
from datetime import datetime, timezone

from ...core.database import fetch_all, execute, get_config
from ...core.config import get_settings

logger = logging.getLogger(__name__)

ASSETS = ["BTC", "ETH", "PAXG"]


async def _get_daily_closes(asset: str, limit: int = 210) -> list[float]:
    """
    Pull up to `limit` daily close prices from TimescaleDB for an asset.
    Uses the continuous aggregate if available, else falls back to raw data.
    """
    rows = await fetch_all(
        """
        SELECT time_bucket('1 day', time) AS day, last(price, time) AS close
        FROM market_prices
        WHERE symbol = $1
        GROUP BY day
        ORDER BY day DESC
        LIMIT $2
        """,
        asset,
        limit,
    )
    # Return oldest-first so MA calculation is chronological
    return [float(r["close"]) for r in reversed(rows)]


def _sma(prices: list[float], period: int) -> list[float]:
    """Simple moving average — returns values aligned to price index."""
    result: list[float] = []
    for i in range(len(prices)):
        if i < period - 1:
            result.append(float("nan"))
        else:
            result.append(sum(prices[i - period + 1 : i + 1]) / period)
    return result


async def _check_golden_cross(asset: str) -> dict | None:
    """
    Detects a Golden Cross or Death Cross on the latest two daily candles.
    Returns a signal dict if a cross occurred, else None.
    """
    closes = await _get_daily_closes(asset, limit=210)
    if len(closes) < 201:
        logger.debug(f"Not enough data for MA cross on {asset} ({len(closes)} days)")
        return None

    ma50 = _sma(closes, 50)
    ma200 = _sma(closes, 200)

    # Latest and previous bars
    prev_diff = ma50[-2] - ma200[-2]
    curr_diff = ma50[-1] - ma200[-1]

    cross_type: str | None = None
    if prev_diff <= 0 and curr_diff > 0:
        cross_type = "GOLDEN_CROSS"
    elif prev_diff >= 0 and curr_diff < 0:
        cross_type = "DEATH_CROSS"

    if cross_type is None:
        return None

    confidence = min(abs(curr_diff) / ma200[-1], 0.99) if ma200[-1] else 0.5

    return {
        "signal_type": cross_type,
        "asset": asset,
        "confidence": round(confidence, 2),
        "data": {
            "ma50": round(ma50[-1], 2),
            "ma200": round(ma200[-1], 2),
            "price": closes[-1],
        },
    }


async def _check_rebalance(asset: str, allocation: float, target: float, threshold: float) -> dict | None:
    drift = allocation - target
    if abs(drift) < threshold:
        return None

    direction = "above" if drift > 0 else "below"
    confidence = min(abs(drift) / 20.0, 0.99)  # saturates at 20% drift

    return {
        "signal_type": "REBALANCE",
        "asset": asset,
        "confidence": round(confidence, 2),
        "data": {
            "allocation": round(allocation, 2),
            "target": round(target, 2),
            "drift": round(drift, 2),
            "direction": direction,
        },
    }


async def _store_signal(signal: dict) -> None:
    """Insert a signal only if no identical un-actioned signal exists for today."""
    existing = await fetch_all(
        """
        SELECT id FROM signals
        WHERE signal_type = $1
          AND asset = $2
          AND actioned = FALSE
          AND time > NOW() - INTERVAL '24 hours'
        """,
        signal["signal_type"],
        signal.get("asset"),
    )
    if existing:
        logger.debug(f"Signal {signal['signal_type']} for {signal.get('asset')} already active, skipping")
        return

    await execute(
        """
        INSERT INTO signals (signal_type, asset, confidence, data)
        VALUES ($1, $2, $3, $4)
        """,
        signal["signal_type"],
        signal.get("asset"),
        signal["confidence"],
        json.dumps(signal.get("data", {})),
    )
    logger.info(f"New signal: {signal['signal_type']} {signal.get('asset')} (conf={signal['confidence']})")

    # Broadcast to WebSocket clients
    try:
        from ...api.websocket import broadcast
        await broadcast({"event": "new_signal", "data": signal})
    except Exception:
        pass


async def compute_and_store_signals() -> list[dict]:
    """
    Main scheduler entry-point.
    Runs all signal checks and persists new signals.
    Returns list of signals that were detected.
    """
    settings = get_settings()
    threshold = settings.rebalance_drift_threshold
    detected: list[dict] = []

    # 1. Golden / Death Cross per asset
    for asset in ASSETS:
        try:
            sig = await _check_golden_cross(asset)
            if sig:
                await _store_signal(sig)
                detected.append(sig)
        except Exception as e:
            logger.warning(f"MA cross check failed for {asset}: {e}")

    # 2. Rebalance alerts — need current allocations
    try:
        from .portfolio import get_portfolio_snapshot
        snapshot = await get_portfolio_snapshot()
        targets = snapshot.get("targets", {})

        for pos in snapshot.get("positions", []):
            asset = pos["asset"]
            target = targets.get(asset, 0.0)
            sig = await _check_rebalance(asset, pos["allocation"], target, threshold)
            if sig:
                await _store_signal(sig)
                detected.append(sig)
    except Exception as e:
        logger.warning(f"Rebalance check failed: {e}")

    return detected
