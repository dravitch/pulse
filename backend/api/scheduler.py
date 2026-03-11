import asyncio
import logging
from apscheduler.schedulers.asyncio import AsyncIOScheduler
from apscheduler.triggers.interval import IntervalTrigger
from ..core.config import get_settings

logger = logging.getLogger(__name__)
_scheduler = AsyncIOScheduler()


async def _fetch_prices():
    from ..modules.finpulse.exchanges import fetch_and_store_prices
    try:
        await fetch_and_store_prices()
    except Exception as e:
        logger.error(f"Price fetch failed: {e}")


async def _snapshot_portfolio():
    from ..modules.finpulse.portfolio import snapshot_portfolio
    try:
        await snapshot_portfolio()
    except Exception as e:
        logger.error(f"Portfolio snapshot failed: {e}")


async def _fetch_rss():
    from ..modules.newspulse.rss_fetcher import fetch_and_store_feeds
    try:
        await fetch_and_store_feeds()
    except Exception as e:
        logger.error(f"RSS fetch failed: {e}")


async def _compute_signals():
    from ..modules.finpulse.signals import compute_and_store_signals
    try:
        await compute_and_store_signals()
    except Exception as e:
        logger.error(f"Signal computation failed: {e}")


async def _boot_fetch():
    """
    Runs once at startup (fire-and-forget).
    Ensures /api/prices/current is never empty on first request.
    """
    logger.info("Boot fetch: pulling initial prices...")
    await _fetch_prices()
    await _snapshot_portfolio()
    logger.info("Boot fetch complete — prices live")


def start_scheduler():
    settings = get_settings()

    # ── Recurring jobs ──────────────────────────────────────────────────────
    _scheduler.add_job(
        _fetch_prices,
        IntervalTrigger(minutes=settings.price_fetch_interval_minutes),
        id="fetch_prices",
        replace_existing=True,
    )

    _scheduler.add_job(
        _snapshot_portfolio,
        IntervalTrigger(minutes=settings.price_fetch_interval_minutes),
        id="snapshot_portfolio",
        replace_existing=True,
    )

    _scheduler.add_job(
        _fetch_rss,
        IntervalTrigger(minutes=settings.rss_fetch_interval_minutes),
        id="fetch_rss",
        replace_existing=True,
    )

    _scheduler.add_job(
        _compute_signals,
        IntervalTrigger(hours=1),
        id="compute_signals",
        replace_existing=True,
    )

    _scheduler.start()
    logger.info(
        f"Scheduler started — prices every {settings.price_fetch_interval_minutes}min, "
        f"RSS every {settings.rss_fetch_interval_minutes}min"
    )

    # ── Immediate boot fetch (non-blocking) ─────────────────────────────────
    loop = asyncio.get_event_loop()
    loop.create_task(_boot_fetch())
