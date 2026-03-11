from datetime import datetime, timezone, timedelta
from fastapi import APIRouter, HTTPException
from pydantic import BaseModel
from typing import Optional
from ..core.database import fetch_all, fetch_one, execute, get_config
from ..core.claude_kernel import ClaudeKernel

router = APIRouter()
kernel = ClaudeKernel()


# ─── HEALTH ────────────────────────────────────────────────────────────────

@router.get("/health")
async def health():
    return {"status": "ok", "service": "PULSE"}


# ─── PORTFOLIO ─────────────────────────────────────────────────────────────

@router.get("/portfolio")
async def get_portfolio():
    """Latest portfolio positions with live prices and drift."""
    from ..modules.finpulse.portfolio import get_portfolio_snapshot
    return await get_portfolio_snapshot()


@router.get("/portfolio/insight")
async def get_portfolio_insight():
    """AI-generated daily brief."""
    portfolio = await get_portfolio()
    positions = {p["asset"]: p for p in portfolio["positions"]}

    data = {
        "total_value": portfolio["total_value"],
        "btc_allocation": positions.get("BTC", {}).get("allocation", 0),
        "eth_allocation": positions.get("ETH", {}).get("allocation", 0),
        "paxg_allocation": positions.get("PAXG", {}).get("allocation", 0),
        "drift": portfolio.get("max_drift", 0),
        "change_24h": 0,
    }

    insight = await kernel.generate_portfolio_insight(data)
    return {"insight": insight, "portfolio": data}


# ─── PRICES ────────────────────────────────────────────────────────────────

@router.get("/prices/current")
async def get_current_prices():
    """
    Primary price endpoint.
    Strategy:
    1. Return from DB if data is < 10 min old (fast, cached)
    2. Else hit the exchange live and store the result
    Always returns within ~2s.
    """
    from ..modules.finpulse.exchanges import (
        get_latest_prices_from_db,
        fetch_and_store_prices,
    )

    db_prices = await get_latest_prices_from_db()
    stale_cutoff = (datetime.now(timezone.utc) - timedelta(minutes=10)).isoformat()

    fresh = {
        asset: data
        for asset, data in db_prices.items()
        if data.get("time", "") >= stale_cutoff
    }

    if len(fresh) == 3:
        return {
            "source": "cache",
            "prices": fresh,
            "fetched_at": datetime.now(timezone.utc).isoformat(),
        }

    # Stale or first boot — fetch live and store
    live_prices = await fetch_and_store_prices()
    now_iso = datetime.now(timezone.utc).isoformat()
    return {
        "source": "live",
        "prices": {
            asset: {"price": price, "time": now_iso}
            for asset, price in live_prices.items()
            if price is not None
        },
        "fetched_at": now_iso,
    }


@router.get("/prices/latest/all")
async def get_latest_prices():
    rows = await fetch_all("""
        SELECT DISTINCT ON (symbol) symbol, price, volume_24h, time
        FROM market_prices
        ORDER BY symbol, time DESC
    """)
    return {"prices": [dict(r) for r in rows]}


@router.get("/prices/{symbol}")
async def get_prices(symbol: str, limit: int = 100):
    rows = await fetch_all("""
        SELECT time, price, volume_24h
        FROM market_prices
        WHERE symbol = $1
        ORDER BY time DESC
        LIMIT $2
    """, symbol.upper(), limit)
    return {"symbol": symbol.upper(), "prices": [dict(r) for r in rows]}


# ─── SIGNALS ───────────────────────────────────────────────────────────────

@router.get("/signals")
async def get_signals(limit: int = 20):
    rows = await fetch_all("""
        SELECT id, time, signal_type, asset, confidence, data, actioned
        FROM signals
        ORDER BY time DESC
        LIMIT $1
    """, limit)
    return {"signals": [dict(r) for r in rows]}


@router.post("/signals/{signal_id}/action")
async def action_signal(signal_id: int):
    await execute("UPDATE signals SET actioned = TRUE WHERE id = $1", signal_id)
    return {"ok": True}


# ─── DCA ───────────────────────────────────────────────────────────────────

class DCAConfig(BaseModel):
    asset: str
    monthly_amount: float
    periods: int = 60  # months


@router.post("/dca/backtest")
async def run_dca_backtest(config: DCAConfig):
    from ..modules.finpulse.dca_engine import DCAEngine
    engine = DCAEngine()
    result = await engine.backtest_level1(
        asset=config.asset.upper(),
        monthly_amount=config.monthly_amount,
        periods=config.periods,
    )
    return result


@router.get("/dca/transactions")
async def get_dca_transactions(asset: Optional[str] = None):
    if asset:
        rows = await fetch_all(
            "SELECT * FROM dca_transactions WHERE asset = $1 ORDER BY time DESC",
            asset.upper()
        )
    else:
        rows = await fetch_all("SELECT * FROM dca_transactions ORDER BY time DESC")
    return {"transactions": [dict(r) for r in rows]}


# ─── NEWS ──────────────────────────────────────────────────────────────────

@router.get("/news")
async def get_news(limit: int = 50, unread_only: bool = False):
    query = """
        SELECT id, fetched_at, source, title, url, published,
               relevance_score, read, archived, summary
        FROM rss_articles
        WHERE archived = FALSE
    """
    params: list = []
    if unread_only:
        query += " AND read = FALSE"
    query += f" ORDER BY relevance_score DESC NULLS LAST, fetched_at DESC LIMIT ${len(params)+1}"
    params.append(limit)

    rows = await fetch_all(query, *params)
    return {"articles": [dict(r) for r in rows]}


@router.post("/news/{article_id}/read")
async def mark_read(article_id: int):
    await execute("UPDATE rss_articles SET read = TRUE WHERE id = $1", article_id)
    return {"ok": True}


@router.post("/news/{article_id}/archive")
async def archive_article(article_id: int):
    await execute("UPDATE rss_articles SET archived = TRUE WHERE id = $1", article_id)
    return {"ok": True}


@router.get("/news/digest/{digest_type}")
async def get_digest(digest_type: str):
    if digest_type not in ("morning", "evening"):
        raise HTTPException(400, "digest_type must be 'morning' or 'evening'")
    limit = 5 if digest_type == "morning" else 10
    rows = await fetch_all("""
        SELECT id, source, title, url, relevance_score, summary
        FROM rss_articles
        WHERE archived = FALSE AND relevance_score >= 0.7
        ORDER BY fetched_at DESC
        LIMIT $1
    """, limit)
    articles = [dict(r) for r in rows]
    digest = await kernel.generate_digest(articles, digest_type)
    return {"digest_type": digest_type, "articles": articles, "summary": digest}


# ─── CLAUDE CHAT ───────────────────────────────────────────────────────────

class ChatMessage(BaseModel):
    message: str


@router.post("/chat")
async def chat(body: ChatMessage):
    portfolio = await get_portfolio()
    signals_rows = await fetch_all(
        "SELECT signal_type, asset, confidence FROM signals ORDER BY time DESC LIMIT 5"
    )
    news_rows = await fetch_all(
        "SELECT title, source FROM rss_articles WHERE relevance_score >= 0.7 ORDER BY fetched_at DESC LIMIT 5"
    )

    context = {
        "portfolio": {
            "total_value": portfolio["total_value"],
            "btc_allocation": next((p["allocation"] for p in portfolio["positions"] if p["asset"] == "BTC"), 0),
            "eth_allocation": next((p["allocation"] for p in portfolio["positions"] if p["asset"] == "ETH"), 0),
            "paxg_allocation": next((p["allocation"] for p in portfolio["positions"] if p["asset"] == "PAXG"), 0),
            "change_24h": 0,
        },
        "signals": [dict(r) for r in signals_rows],
        "top_news": [dict(r) for r in news_rows],
    }

    response = await kernel.chat(body.message, context)
    return {"response": response}


# ─── CONFIG ────────────────────────────────────────────────────────────────

@router.get("/config/{key}")
async def read_config(key: str):
    value = await get_config(key)
    if value is None:
        raise HTTPException(404, f"Config key '{key}' not found")
    return {"key": key, "value": value}


# ─── MANUAL TRIGGER (dev/debug) ────────────────────────────────────────────

@router.post("/admin/fetch-prices")
async def admin_fetch_prices():
    """Manually trigger a price fetch. Useful for testing without waiting for scheduler."""
    from ..modules.finpulse.exchanges import fetch_and_store_prices
    prices = await fetch_and_store_prices()
    return {"ok": True, "prices": prices}
