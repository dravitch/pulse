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

        prompt = f"""Évalue {len(articles)} articles pour un investisseur intéressé par : {', '.join(user_interests)}.

Réponds UNIQUEMENT avec un tableau JSON, sans autre texte :
[{{"article_num": 1, "score": 0.85, "reason": "analyse stratégie DCA Bitcoin"}}]

Score 0.0 à 1.0 :
- 0.9-1.0 : très pertinent, impact direct sur le portefeuille
- 0.7-0.89 : pertinent, contexte utile
- 0.5-0.69 : lien indirect
- 0.0-0.49 : hors sujet

Articles :
{self._format_articles(articles)}"""

        try:
            response = self.client.messages.create(
                model=self.model,
                max_tokens=1500,
                messages=[{"role": "user", "content": prompt}],
            )
            raw = response.content[0].text.strip()
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
            logger.error(f"Claude filter_news erreur de parsing : {e}")
            return []

    async def generate_portfolio_insight(self, portfolio_data: dict) -> str:
        """Génère un bref quotidien 2-3 phrases sur le portefeuille."""
        prompt = f"""Portefeuille actuel :
- Valeur totale : {portfolio_data.get('total_value', 0):,.2f} $
- BTC : {portfolio_data.get('btc_allocation', 0):.1f}% (cible 60%)
- ETH : {portfolio_data.get('eth_allocation', 0):.1f}% (cible 30%)
- PAXG : {portfolio_data.get('paxg_allocation', 0):.1f}% (cible 10%)
- Écart maximal : {portfolio_data.get('drift', 0):.1f}%
- Variation 24h : {portfolio_data.get('change_24h', 0):+.2f}%

Rédige un bref quotidien en 3 points courts et directs :
• Performance : état du portefeuille
• Allocation : drift vs cibles
• Action : recommandation concrète (ou "aucune action requise")

Réponds en français, sans titre, sans markdown, juste les 3 points avec •."""

        response = self.client.messages.create(
            model=self.model,
            max_tokens=300,
            messages=[{"role": "user", "content": prompt}],
        )
        return response.content[0].text.strip()

    async def generate_digest(self, articles: list[dict], digest_type: str) -> str:
        """Génère le digest matin (5 articles) ou soir (10 articles)."""
        limit = 5 if digest_type == "morning" else 10
        top = sorted(articles, key=lambda x: x.get("relevance_score", 0), reverse=True)[:limit]

        label = "matinal" if digest_type == "morning" else "du soir"
        items = "\n".join(
            f"{i}. [{a.get('source')}] {a.get('title')}"
            for i, a in enumerate(top, 1)
        )

        prompt = f"""Rédige un digest {label} à partir de ces {len(top)} articles crypto.
Pour chaque article, une phrase de synthèse concise et directe.
En français, sans markdown, sans gras, juste une liste numérotée.

Articles :
{items}"""

        response = self.client.messages.create(
            model=self.model,
            max_tokens=800,
            messages=[{"role": "user", "content": prompt}],
        )
        return response.content[0].text.strip()

    async def chat(self, message: str, context: dict) -> str:
        """Chat contextuel avec accès au portefeuille et aux actualités."""
        portfolio = context.get("portfolio", {})
        recent_signals = context.get("signals", [])
        top_news = context.get("top_news", [])

        system = f"""Tu es PULSE, un assistant personnel spécialisé en finance crypto et veille d'actualités.

Portefeuille actuel :
- Valeur totale : {portfolio.get('total_value', 0):,.2f} $
- BTC : {portfolio.get('btc_allocation', 0):.1f}% | ETH : {portfolio.get('eth_allocation', 0):.1f}% | PAXG : {portfolio.get('paxg_allocation', 0):.1f}%
- Variation 24h : {portfolio.get('change_24h', 0):+.2f}%

Signaux actifs : {len(recent_signals)} ({', '.join(s.get('signal_type','') for s in recent_signals[:3])})

Actualités du jour : {', '.join(a.get('title','')[:60] for a in top_news[:3])}

Règles de réponse :
- Réponds toujours en français
- Sois direct, factuel et quantitatif
- Pas de markdown (pas de **, pas de #)
- Utilise des retours à la ligne pour structurer
- Maximum 4-5 phrases sauf si une analyse détaillée est demandée"""

        response = self.client.messages.create(
            model=self.model,
            max_tokens=600,
            system=system,
            messages=[{"role": "user", "content": message}],
        )
        return response.content[0].text.strip()
