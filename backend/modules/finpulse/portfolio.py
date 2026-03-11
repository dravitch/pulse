"""
Portfolio snapshot helpers.

Responsibilities:
- Compute current allocations from the latest position rows.
- Detect drift vs target allocations.
- Snapshot current state into portfolio_positions (time-series).
"""

import logging
from datetime import datetime, timezone
from typing import Optional

from ...core.database import fetch_all, execute_many, get_config
from .exchanges import get_latest_prices_from_db

logger = logging.getLogger(__name__)

# Default targets if not set in DB
DEFAULT_TARGETS: dict[str, float] = {"BTC": 60.0, "ETH": 30.0, "PAXG": 10.0}


async def get_targets() -> dict[str, float]:
    cfg = await get_config("portfolio_targets")
    if isinstance(cfg, dict):
        return {k: float(v) for k, v in cfg.items()}
    return DEFAULT_TARGETS


async def get_portfolio_snapshot() -> dict:
    """
    Build a full portfolio snapshot:
    - latest units per asset from portfolio_positions
    - current market prices
    - allocations + drift vs targets
    """
    positions_rows = await fetch_all("""
        SELECT DISTINCT ON (asset)
            asset, units, avg_cost_basis, current_value, time
        FROM portfolio_positions
        ORDER BY asset, time DESC
    """)

    prices = await get_latest_prices_from_db()
    targets = await get_targets()

    positions: list[dict] = []
    total_value: float = 0.0

    for row in positions_rows:
        asset = row["asset"]
        units = float(row["units"])
        price_data = prices.get(asset)
        price = price_data["price"] if price_data else float(row["current_value"]) / units if units else 0

        current_value = units * price
        total_value += current_value

        positions.append({
            "asset": asset,
            "units": units,
            "avg_cost_basis": float(row["avg_cost_basis"]),
            "current_value": current_value,
            "price": price,
            "allocation": 0.0,  # filled below
            "target": targets.get(asset, 0.0),
            "drift": 0.0,  # filled below
        })

    # Compute allocations & drift
    for p in positions:
        p["allocation"] = (p["current_value"] / total_value * 100) if total_value else 0.0
        p["drift"] = p["allocation"] - p["target"]

    max_drift = max((abs(p["drift"]) for p in positions), default=0.0)

    return {
        "total_value": total_value,
        "positions": positions,
        "max_drift": max_drift,
        "needs_rebalance": max_drift > 5.0,
        "prices": prices,
        "targets": targets,
    }


async def snapshot_portfolio() -> None:
    """
    Called by the scheduler after each price fetch.
    Reads current units from DB, updates current_value with live price,
    then inserts a new time-series row.
    """
    snapshot = await get_portfolio_snapshot()
    now = datetime.now(timezone.utc)

    rows = [
        (
            now,
            p["asset"],
            p["units"],
            p["avg_cost_basis"],
            p["current_value"],
        )
        for p in snapshot["positions"]
        if p["units"] > 0
    ]

    if rows:
        await execute_many(
            """
            INSERT INTO portfolio_positions (time, asset, units, avg_cost_basis, current_value)
            VALUES ($1, $2, $3, $4, $5)
            ON CONFLICT (time, asset) DO UPDATE
                SET current_value = EXCLUDED.current_value
            """,
            rows,
        )
        logger.debug(f"Portfolio snapshot stored: total=${snapshot['total_value']:,.2f}")


async def upsert_position(
    asset: str,
    units: float,
    avg_cost_basis: float,
    current_price: Optional[float] = None,
) -> None:
    """
    Add or update a manual position entry.
    Used when recording a DCA buy or manual portfolio import.
    """
    if current_price is None:
        prices = await get_latest_prices_from_db()
        current_price = prices.get(asset.upper(), {}).get("price", 0.0)

    current_value = units * current_price
    now = datetime.now(timezone.utc)

    await execute_many(
        """
        INSERT INTO portfolio_positions (time, asset, units, avg_cost_basis, current_value)
        VALUES ($1, $2, $3, $4, $5)
        """,
        [(now, asset.upper(), units, avg_cost_basis, current_value)],
    )
