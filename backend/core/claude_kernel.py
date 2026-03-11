import json
import logging
from anthropic import Anthropic
from .config import get_settings

logger = logging.getLogger(__name__)


class ClaudeKernel:
    def __init__(self):
        settings = get_settings()
        self.client = Anthropic(api_key=settings.anthropic_api_key)
        self.model = settings.claude_model
        self.max_tokens = settings.claude_max_tokens

    def _format_articles(self, articles: list[dict]) -> str:
        lines = []
        for i, a in enumerate(articles, 1):
            lines.append(f"{i}. [{a.get('source', '?')}] {a.get('title', '')}")
            if a.get("content"):
                lines.append(f"   {a['content'][:200]}...")
        return "\n".join(lines)

    async def filter_news(self, articles: list[dict], user_interests: list[str]) -> list[dict]:
        """Score articles by relevance, return only those above threshold."""
        if not articles:
            return []

        prompt = f"""Filter {len(articles)} articles for a user interested in: {', '.join(user_interests)}.

Return ONLY a JSON array, no other text:
[{{"article_num": 1, "score": 0.85, "reason": "directly covers Bitcoin DCA strategy"}}]

Score 0.0-1.0 where:
- 0.9-1.0: highly relevant, directly about user interests
- 0.7-0.89: relevant, useful context
- 0.5-0.69: tangentially related
- 0.0-0.49: not relevant

Articles:
{self._format_articles(articles)}"""

        try:
            response = self.client.messages.create(
                model=self.model,
                max_tokens=1500,
                messages=[{"role": "user", "content": prompt}],
            )
            raw = response.content[0].text.strip()
            # Extract JSON array if wrapped in markdown
            if "```" in raw:
                raw = raw.split("```")[1].lstrip("json").strip()
            scores = json.loads(raw)

            for item in scores:
                idx = item["article_num"] - 1
                if 0 <= idx < len(articles):
                    articles[idx]["relevance_score"] = float(item["score"])
                    articles[idx]["score_reason"] = item.get("reason", "")

            settings = get_settings()
            threshold = settings.news_relevance_threshold
            return [a for a in articles if a.get("relevance_score", 0) >= threshold]

        except (json.JSONDecodeError, KeyError) as e:
            logger.error(f"Claude filter_news parse error: {e}")
            return []

    async def generate_portfolio_insight(self, portfolio_data: dict) -> str:
        """Generate a 2-3 sentence daily brief for the portfolio."""
        prompt = f"""Portfolio snapshot:
- Total value: ${portfolio_data.get('total_value', 0):,.2f}
- BTC: {portfolio_data.get('btc_allocation', 0):.1f}% (target: 60%)
- ETH: {portfolio_data.get('eth_allocation', 0):.1f}% (target: 30%)
- PAXG: {portfolio_data.get('paxg_allocation', 0):.1f}% (target: 10%)
- Largest drift: {portfolio_data.get('drift', 0):.1f}%
- 24h change: {portfolio_data.get('change_24h', 0):+.2f}%

Write a concise 2-3 sentence daily brief covering: performance, drift status, and one actionable recommendation. Be direct and quantitative."""

        response = self.client.messages.create(
            model=self.model,
            max_tokens=300,
            messages=[{"role": "user", "content": prompt}],
        )
        return response.content[0].text.strip()

    async def generate_digest(self, articles: list[dict], digest_type: str) -> str:
        """Generate morning (top 5) or evening (top 10) digest."""
        limit = 5 if digest_type == "morning" else 10
        top = sorted(articles, key=lambda x: x.get("relevance_score", 0), reverse=True)[:limit]

        items = "\n".join(
            f"{i}. [{a.get('source')}] {a.get('title')}"
            for i, a in enumerate(top, 1)
        )

        prompt = f"""Create a {digest_type} news digest from these {len(top)} articles.
For each article write a 1-2 sentence summary. Be concise and informative.

Articles:
{items}

Format: numbered list matching the order above."""

        response = self.client.messages.create(
            model=self.model,
            max_tokens=800,
            messages=[{"role": "user", "content": prompt}],
        )
        return response.content[0].text.strip()

    async def chat(self, message: str, context: dict) -> str:
        """Context-aware chat with access to portfolio and news data."""
        portfolio = context.get("portfolio", {})
        recent_signals = context.get("signals", [])
        top_news = context.get("top_news", [])

        system = f"""You are PULSE, a personal finance and news intelligence assistant.

Current portfolio:
- Total value: ${portfolio.get('total_value', 0):,.2f}
- BTC: {portfolio.get('btc_allocation', 0):.1f}% | ETH: {portfolio.get('eth_allocation', 0):.1f}% | PAXG: {portfolio.get('paxg_allocation', 0):.1f}%
- 24h change: {portfolio.get('change_24h', 0):+.2f}%

Active signals: {len(recent_signals)} ({', '.join(s.get('signal_type','') for s in recent_signals[:3])})

Top news today: {', '.join(a.get('title','')[:60] for a in top_news[:3])}

Be direct, data-driven, and actionable. No fluff."""

        response = self.client.messages.create(
            model=self.model,
            max_tokens=600,
            system=system,
            messages=[{"role": "user", "content": message}],
        )
        return response.content[0].text.strip()
