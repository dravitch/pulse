"""
NewsPulse RSS fetcher.

Fetches articles from French and major crypto news sources,
deduplicates by URL, scores with Claude, and stores in rss_articles.
"""
import logging
from datetime import datetime, timezone
from email.utils import parsedate_to_datetime

import feedparser
import httpx

from ...core.database import execute, fetch_one
from ...core.config import get_settings

logger = logging.getLogger(__name__)

# ─── RSS Feeds ──────────────────────────────────────────────────────────────

FEEDS = [
    # French sources
    {"source": "Journal du Coin",  "url": "https://journalducoin.com/feed/"},
    {"source": "Cryptoast",        "url": "https://cryptoast.fr/feed/"},
    {"source": "CoinAct",          "url": "https://coinactu.com/feed/"},
    {"source": "Bitcoin.fr",       "url": "https://bitcoin.fr/feed/"},
    # English sources (major signals)
    {"source": "CoinDesk",         "url": "https://www.coindesk.com/arc/outboundfeeds/rss/"},
    {"source": "CoinTelegraph",    "url": "https://cointelegraph.com/rss"},
    {"source": "The Block",        "url": "https://www.theblock.co/rss.xml"},
]

# Keywords to pre-filter articles (keep only relevant ones before Claude scoring)
RELEVANT_KEYWORDS = {
    "bitcoin", "btc", "ethereum", "eth", "crypto", "blockchain",
    "defi", "nft", "altcoin", "binance", "coinbase", "stablecoin",
    "paxg", "or", "gold", "halving", "dca", "portefeuille", "wallet",
    "regulation", "sec", "bce", "fed", "inflation", "marché", "market",
}


def _parse_date(entry: dict) -> datetime | None:
    """Try to extract a publish date from a feed entry."""
    for field in ("published", "updated", "created"):
        raw = entry.get(field)
        if raw:
            try:
                return parsedate_to_datetime(raw).astimezone(timezone.utc)
            except Exception:
                pass
    return None


def _is_relevant(title: str, content: str) -> bool:
    """Quick keyword pre-filter before sending to Claude."""
    text = (title + " " + content).lower()
    return any(kw in text for kw in RELEVANT_KEYWORDS)


async def _fetch_feed(source: str, feed_url: str) -> list[dict]:
    """Fetch and parse a single RSS feed. Returns list of article dicts."""
    articles = []
    try:
        async with httpx.AsyncClient(timeout=15, follow_redirects=True) as client:
            resp = await client.get(feed_url, headers={"User-Agent": "PULSE/0.1 RSS Reader"})
            resp.raise_for_status()
            feed = feedparser.parse(resp.text)

        for entry in feed.entries[:20]:  # cap at 20 per feed
            title = entry.get("title", "").strip()
            url = entry.get("link", "").strip()
            if not title or not url:
                continue

            content = entry.get("summary", "") or entry.get("content", [{}])[0].get("value", "")
            # Strip basic HTML tags
            import re
            content = re.sub(r"<[^>]+>", " ", content).strip()[:500]

            if not _is_relevant(title, content):
                continue

            articles.append({
                "source": source,
                "title": title,
                "url": url,
                "published": _parse_date(entry),
                "content": content,
            })

    except Exception as exc:
        logger.warning(f"Feed fetch failed [{source}]: {exc}")

    return articles


async def _score_articles(articles: list[dict]) -> list[dict]:
    """Score articles using Claude for crypto portfolio relevance."""
    if not articles:
        return []

    try:
        from ...core.claude_kernel import ClaudeKernel
        kernel = ClaudeKernel()
        interests = ["Bitcoin", "Ethereum", "PAXG", "DCA", "régulation crypto", "macroéconomie"]
        return await kernel.filter_news(articles, interests)
    except Exception as exc:
        logger.error(f"Claude scoring failed: {exc}")
        # Return articles with default score so they still appear
        for a in articles:
            a["relevance_score"] = 0.5
        return articles


async def _store_article(article: dict) -> bool:
    """Insert article if URL not already in DB. Returns True if inserted."""
    existing = await fetch_one("SELECT id FROM rss_articles WHERE url = $1", article["url"])
    if existing:
        return False

    await execute(
        """
        INSERT INTO rss_articles
            (fetched_at, source, title, url, published, content, relevance_score, summary)
        VALUES
            (NOW(), $1, $2, $3, $4, $5, $6, $7)
        """,
        article["source"],
        article["title"],
        article["url"],
        article.get("published"),
        article.get("content"),
        article.get("relevance_score"),
        article.get("score_reason"),  # brief reason used as summary
    )
    return True


async def fetch_and_store_feeds() -> int:
    """
    Main entry-point called by the scheduler every 15 minutes.
    Fetches all feeds, scores with Claude, deduplicates, stores.
    Returns count of new articles stored.
    """
    settings = get_settings()

    # 1. Fetch all feeds concurrently
    import asyncio
    tasks = [_fetch_feed(f["source"], f["url"]) for f in FEEDS]
    results = await asyncio.gather(*tasks, return_exceptions=True)

    all_articles: list[dict] = []
    for res in results:
        if isinstance(res, list):
            all_articles.extend(res)

    if not all_articles:
        logger.info("RSS: no new articles from any feed")
        return 0

    logger.info(f"RSS: fetched {len(all_articles)} candidate articles")

    # 2. Score with Claude (batch)
    batch_size = settings.news_batch_size
    scored: list[dict] = []
    for i in range(0, len(all_articles), batch_size):
        batch = all_articles[i:i + batch_size]
        scored.extend(await _score_articles(batch))

    # 3. Store new articles
    stored = 0
    for article in scored:
        if await _store_article(article):
            stored += 1

    logger.info(f"RSS: stored {stored} new articles (scored {len(scored)})")
    return stored
