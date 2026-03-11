# PULSE — Documentation Technique
> Personal Intelligence OS — Finance crypto & veille d'actualités
> Version MVP Phase 2 — Mars 2026

---

## Table des matières

1. [Vue d'ensemble du projet](#1-vue-densemble)
2. [Architecture](#2-architecture)
3. [Prérequis et installation](#3-prérequis-et-installation)
4. [Structure des fichiers](#4-structure-des-fichiers)
5. [Modules backend](#5-modules-backend)
6. [Frontend](#6-frontend)
7. [Base de données](#7-base-de-données)
8. [Scheduler (tâches planifiées)](#8-scheduler)
9. [Configuration (.env)](#9-configuration-env)
10. [Commandes utiles](#10-commandes-utiles)
11. [Leçons apprises](#11-leçons-apprises)
12. [Roadmap Phase 3](#12-roadmap-phase-3)

---

## 1. Vue d'ensemble

PULSE est un OS personnel de veille et de gestion de portefeuille crypto.
Il agrège des actualités depuis des flux RSS, les filtre par pertinence via Claude (Anthropic),
suit un portefeuille BTC/ETH/PAXG avec des prix en temps réel depuis Binance,
et expose un assistant conversationnel contextuel.

**Modules principaux :**
- **FinPulse** — portefeuille live, prix Binance, drift, P&L, insights Claude
- **NewsPulse** — RSS crypto (FR + EN), scoring Claude, lecture/archivage, digest matinal/soir
- **Claude Chat** — assistant contextuel avec accès portefeuille + actualités du jour

---

## 2. Architecture

```
┌─────────────────────────────────────────────────┐
│                  Frontend (React)                │
│   Vite 5 · TypeScript · Tailwind CSS v3         │
│   Port 5173                                     │
└───────────────────────┬─────────────────────────┘
                        │ HTTP / WebSocket
┌───────────────────────▼─────────────────────────┐
│               Backend (FastAPI)                  │
│   Python 3.11 · Uvicorn · APScheduler           │
│   Port 8000                                     │
│                                                 │
│  ┌─────────────┐  ┌──────────────┐              │
│  │  FinPulse   │  │  NewsPulse   │              │
│  │  exchanges  │  │  rss_fetcher │              │
│  │  portfolio  │  │              │              │
│  │  signals    │  │              │              │
│  └──────┬──────┘  └──────┬───────┘              │
│         │                │                      │
│  ┌──────▼────────────────▼───────┐              │
│  │       ClaudeKernel            │              │
│  │  (Anthropic claude-sonnet)    │              │
│  └───────────────────────────────┘              │
└───────────────────────┬─────────────────────────┘
                        │ asyncpg
┌───────────────────────▼─────────────────────────┐
│          PostgreSQL 18 + TimescaleDB             │
│   Docker · Port 5432                            │
│   Hypertables: market_prices, portfolio_positions│
└─────────────────────────────────────────────────┘
```

**Flux de données :**
1. APScheduler déclenche `fetch_and_store_prices()` toutes les 5 minutes
2. CCXT interroge Binance (endpoint public, sans clé API)
3. Les prix sont stockés dans `market_prices` (hypertable TimescaleDB)
4. `snapshot_portfolio()` recalcule les allocations et le drift
5. Le frontend polling via `/portfolio` toutes les 30 secondes
6. Les actualités RSS sont récupérées toutes les 15 minutes, scorées par Claude, dédupliquées par URL

---

## 3. Prérequis et installation

### Applications requises

| Outil | Version | Usage |
|-------|---------|-------|
| Python | 3.11+ | Backend FastAPI |
| Node.js | 22+ | Frontend Vite/React |
| Docker Desktop | Dernière | PostgreSQL + TimescaleDB |
| Git | Quelconque | Versioning |

### Variables d'environnement (`.env` à la racine de `C:\Pulse`)

```env
DATABASE_URL=postgresql://pulse:pulse@localhost:5432/pulse
ANTHROPIC_API_KEY=sk-ant-xxxxxxxxxxxx
EXCHANGE_ID=binance
CCXT_SANDBOX=false
NEWS_RELEVANCE_THRESHOLD=0.7
NEWS_BATCH_SIZE=20
CLAUDE_MODEL=claude-sonnet-4-5
CLAUDE_MAX_TOKENS=1000
```

### Installation backend

```bash
cd C:\Pulse
python -m venv backend/venv
backend\venv\Scripts\pip install -r backend/requirements.txt
```

### Installation frontend

```bash
cd C:\Pulse\frontend
npm install
```

### Démarrage base de données

```bash
cd C:\Pulse
docker-compose up -d
```

---

## 4. Structure des fichiers

```
C:\Pulse\
├── .env                          # Variables d'environnement (non versionné)
├── docker-compose.yml            # PostgreSQL + TimescaleDB
├── backend/
│   ├── main.py                   # Point d'entrée FastAPI + lifespan
│   ├── requirements.txt
│   ├── venv/                     # Environnement Python (non versionné)
│   ├── api/
│   │   ├── routes.py             # Tous les endpoints REST
│   │   ├── scheduler.py          # APScheduler jobs
│   │   └── websocket.py          # WebSocket broadcast
│   ├── core/
│   │   ├── config.py             # Settings Pydantic (BaseSettings)
│   │   ├── database.py           # Pool asyncpg, helpers execute/fetch
│   │   └── claude_kernel.py      # Anthropic SDK wrapper (FR, sans markdown)
│   └── modules/
│       ├── finpulse/
│       │   ├── exchanges.py      # CCXT async wrapper, Binance prix live
│       │   ├── portfolio.py      # Snapshot, drift, upsert_position
│       │   ├── signals.py        # Détection signaux DCA
│       │   └── dca_engine.py     # Moteur DCA (backtesting + recommandations)
│       └── newspulse/
│           └── rss_fetcher.py    # Fetch RSS, filtre keywords, score Claude, stocke
├── frontend/
│   ├── index.html
│   ├── package.json              # "type": "module" + dépendances
│   ├── tailwind.config.cjs       # CommonJS requis (voir leçons apprises)
│   ├── postcss.config.cjs        # CommonJS avec chemin absolu tailwind
│   ├── vite.config.ts
│   └── src/
│       ├── App.tsx               # Router principal (tabs)
│       ├── hooks/
│       │   └── useApi.ts         # Hook générique fetch + apiFetch helper
│       └── components/
│           ├── Dashboard.tsx     # Vue compacte 3 colonnes
│           ├── FinPulse/
│           │   └── FinPulsePanel.tsx   # Prix live, P&L, drift, insight Claude
│           ├── NewsPulse/
│           │   └── NewsPulsePanel.tsx  # Liste articles, score, digest
│           └── ClaudeChat/
│               └── ClaudeChatPanel.tsx # Chat contextuel
└── docs/
    └── PULSE_DOCUMENTATION.md    # Ce fichier
```

---

## 5. Modules backend

### `core/claude_kernel.py`

Wrapper autour du SDK Anthropic. Toutes les réponses sont en français, sans markdown.

| Méthode | Usage | Tokens max |
|---------|-------|-----------|
| `filter_news(articles, interests)` | Score 0.0-1.0 par article, retourne ceux ≥ seuil | 1500 |
| `generate_portfolio_insight(data)` | 3 bullet points (•) : Performance / Allocation / Action | 300 |
| `generate_digest(articles, type)` | Liste numérotée du brief matinal (5) ou soir (10) | 800 |
| `chat(message, context)` | Chat contextuel portefeuille + news | 600 |

**Important :** Le client Anthropic est synchrone. Les appels sont faits directement (pas d'`async`).
Les méthodes sont déclarées `async` pour compatibilité FastAPI mais utilisent `self.client.messages.create()` de manière synchrone (bloquant sur la boucle d'événements). Pour la production, utiliser `asyncio.to_thread()`.

### `modules/finpulse/exchanges.py`

- CCXT Binance, mode public (pas de clé API)
- `fetch_and_store_prices()` → récupère BTC/ETH/PAXG, stocke dans `market_prices`
- Appels bloquants CCXT wrappés dans `loop.run_in_executor(None, ...)` pour ne pas bloquer l'event loop

### `modules/finpulse/portfolio.py`

- `get_portfolio_snapshot()` → positions + prix live + allocations + drift
- `snapshot_portfolio()` → insère une ligne time-series dans `portfolio_positions`
- `upsert_position()` → pour les achats DCA manuels

### `modules/newspulse/rss_fetcher.py`

Flux configurés :

| Source | Langue | URL |
|--------|--------|-----|
| Journal du Coin | FR | journalducoin.com/feed/ |
| Cryptoast | FR | cryptoast.fr/feed/ |
| CoinAct | FR | coinactu.com/feed/ |
| Bitcoin.fr | FR | bitcoin.fr/feed/ |
| CoinDesk | EN | coindesk.com/arc/outboundfeeds/rss/ |
| CoinTelegraph | EN | cointelegraph.com/rss |
| The Block | EN | theblock.co/rss.xml |

Pipeline : httpx async fetch → feedparser → filtre keywords → Claude scoring → déduplication URL → INSERT DB

---

## 6. Frontend

### Stack

- React 18 + TypeScript + Vite 5
- Tailwind CSS v3 (config `.cjs`)
- Lucide React (icônes)

### Hook `useApi`

```typescript
const { data, loading, error, refetch } = useApi<T>('/endpoint', [deps])
```

Polling automatique toutes les 30s si `deps` vide.
`apiFetch<T>(path, options)` pour les appels ponctuels (POST, etc.).

### Composants principaux

| Composant | Route API | Description |
|-----------|-----------|-------------|
| `FinPulsePanel` | `/portfolio`, `/portfolio/insight` | Prix live, P&L, drift, insight Claude |
| `NewsPulsePanel` | `/news`, `/news/digest/:type` | Articles scorés, brief matinal/soir |
| `ClaudeChatPanel` | `/chat` | Conversation contextuelle |
| `Dashboard` | Agrège les 3 | Vue compacte multi-colonnes |

---

## 7. Base de données

### Docker Compose

```yaml
# PostgreSQL 18 + TimescaleDB
# User: pulse / Password: pulse / DB: pulse
# Port: 5432
```

### Tables principales

```sql
-- Hypertable TimescaleDB (time-series)
market_prices (time TIMESTAMPTZ, symbol TEXT, price NUMERIC)
portfolio_positions (time TIMESTAMPTZ, asset TEXT, units NUMERIC, avg_cost_basis NUMERIC, current_value NUMERIC)

-- Tables standard
rss_articles (id, fetched_at, source, title, url, published, content, relevance_score, summary, read, archived)
dca_signals (id, time, asset, signal_type, price, amount_usd, reason)
app_config (key TEXT PRIMARY KEY, value JSONB)
```

### Seed des positions de démonstration

```sql
INSERT INTO portfolio_positions (time, asset, units, avg_cost_basis, current_value)
VALUES
  (NOW(), 'BTC', 0.4281, 45000, 30000),
  (NOW(), 'ETH', 7.3529, 1800, 15000),
  (NOW(), 'PAXG', 0.9673, 2200,  5000);
```

---

## 8. Scheduler

Défini dans `backend/api/scheduler.py` (APScheduler `AsyncIOScheduler`).

| Job | Fréquence | Fonction |
|-----|-----------|----------|
| Prix marché | 5 min | `fetch_and_store_prices()` |
| Snapshot portefeuille | 5 min | `snapshot_portfolio()` |
| RSS actualités | 15 min | `fetch_and_store_feeds()` |
| Signaux DCA | 1 heure | `detect_and_store_signals()` |

---

## 9. Configuration `.env`

| Variable | Description | Défaut |
|----------|-------------|--------|
| `DATABASE_URL` | URL PostgreSQL avec credentials | — (requis) |
| `ANTHROPIC_API_KEY` | Clé API Anthropic | — (requis) |
| `EXCHANGE_ID` | Exchange CCXT | `binance` |
| `CCXT_SANDBOX` | Mode sandbox CCXT | `false` |
| `NEWS_RELEVANCE_THRESHOLD` | Seuil score Claude (0.0-1.0) | `0.7` |
| `NEWS_BATCH_SIZE` | Articles par batch Claude | `20` |
| `CLAUDE_MODEL` | Modèle Anthropic | `claude-sonnet-4-5` |
| `CLAUDE_MAX_TOKENS` | Tokens max par défaut | `1000` |

---

## 10. Commandes utiles

### Démarrer les services

```bash
# Base de données
docker-compose up -d

# Backend (depuis C:\Pulse)
backend\venv\Scripts\python.exe -m uvicorn backend.main:app --reload --host 127.0.0.1 --port 8000

# Frontend (depuis C:\Pulse\frontend)
npx vite --port 5173
```

### Vérifier les services

```bash
# Santé backend
curl http://127.0.0.1:8000/health

# Prix actuels
curl http://127.0.0.1:8000/api/prices

# Portefeuille
curl http://127.0.0.1:8000/api/portfolio

# Déclencher un fetch RSS immédiat
curl -X POST http://127.0.0.1:8000/api/admin/fetch-news

# Déclencher un fetch prix immédiat
curl -X POST http://127.0.0.1:8000/api/admin/fetch-prices
```

### Base de données

```bash
# Connexion psql
docker exec -it pulse-db psql -U pulse -d pulse

# Vérifier les prix stockés
SELECT symbol, price, time FROM market_prices ORDER BY time DESC LIMIT 10;

# Vérifier les articles RSS
SELECT source, title, relevance_score FROM rss_articles ORDER BY fetched_at DESC LIMIT 10;

# Vider les articles (reset)
TRUNCATE rss_articles;
```

### Git

```bash
# Statut
git status

# Log
git log --oneline -10

# Pousser sur GitHub
git push origin main
```

---

## 11. Leçons apprises

### Windows App Control bloque les `.exe` du venv

**Problème :** `uvicorn.exe` et autres binaires du venv Python bloqués par Windows App Control (AppLocker).
**Solution :** Utiliser `python.exe -m uvicorn` au lieu de `uvicorn.exe` directement.

```bash
# Ne fonctionne pas (bloqué)
backend\venv\Scripts\uvicorn.exe backend.main:app

# Fonctionne
backend\venv\Scripts\python.exe -m uvicorn backend.main:app --reload
```

### Tailwind CSS v3 + `"type": "module"` dans package.json

**Problème :** Tailwind v3 charge sa config avec `require()` (CommonJS). Si `package.json` contient `"type": "module"`, les fichiers `.js` sont traités comme ES modules et `require` échoue silencieusement (aucun style appliqué, warning "content option missing").
**Solution :** Renommer les configs en `.cjs` et utiliser `__dirname` avec `path.join()` pour les chemins absolus.

```js
// tailwind.config.cjs (et non .js)
const path = require('path')
module.exports = {
  content: [
    path.join(__dirname, 'index.html'),
    path.join(__dirname, 'src/**/*.{js,ts,jsx,tsx}'),
  ],
  // ...
}
```

### DATABASE_URL sans credentials

**Problème :** `.env` initial contenait `postgresql://localhost:5432/pulse` sans user/password.
Docker Compose crée l'utilisateur `pulse` avec mot de passe `pulse`.
**Solution :** `postgresql://pulse:pulse@localhost:5432/pulse`

### Vite doit connaître le bon répertoire racine

**Problème :** Lancer Vite depuis `C:\Pulse` au lieu de `C:\Pulse\frontend` → 404 sur tous les assets.
**Solution :** Passer le chemin absolu du frontend comme argument positionnel à `vite.js`.

```
node C:\Pulse\frontend\node_modules\vite\bin\vite.js C:\Pulse\frontend --port 5173
```

### `ModuleNotFoundError: No module named 'backend'`

**Problème :** Uvicorn lancé depuis le mauvais répertoire (`C:\Users\tunnel` au lieu de `C:\Pulse`).
**Solution :** Toujours lancer depuis la racine du projet (`C:\Pulse`).

### Claude SDK est synchrone dans un contexte async

**Problème :** `client.messages.create()` est synchrone et bloque l'event loop FastAPI.
**Impact MVP :** Acceptable (peu de requêtes simultanées).
**Solution production :** Utiliser `asyncio.to_thread(client.messages.create, ...)`.

### `get_config()` retourne une chaîne JSON, pas un dict

**Problème :** `app_config` stocke la valeur en `JSONB`. `get_config()` retourne un `str` Python, pas un `dict`. Appeler `.items()` dessus lève `AttributeError`.
**Solution :** Parser avec `json.loads()` ou utiliser directement les données du snapshot.

### Hot-reload Uvicorn peu fiable sur Windows

**Problème :** `--reload` ne détecte pas toujours les changements de fichiers sur Windows (limitation watchfiles).
**Solution :** Redémarrer manuellement le serveur backend après des modifications importantes.

---

## 12. Roadmap Phase 3

### Fonctionnalités prioritaires

- [ ] **Authentification** — Login simple (token JWT ou session) pour sécuriser l'interface
- [ ] **DCA automatisé** — Exécution réelle d'ordres via clé API Binance (mode lecture seule → lecture/écriture)
- [ ] **Alertes** — Notifications push/email sur signaux DCA ou drift > seuil
- [ ] **Historique graphique** — Charts portefeuille (Chart.js ou Recharts) sur 30/90 jours
- [ ] **Multi-portefeuille** — Support de plusieurs utilisateurs ou portefeuilles

### Améliorations techniques

- [ ] Rendre les appels Claude véritablement async (`asyncio.to_thread`)
- [ ] Cache Redis pour les prix (éviter le polling DB)
- [ ] Rate limiting sur les endpoints API
- [ ] Tests unitaires (pytest + pytest-asyncio)
- [ ] CI/CD GitHub Actions (lint + tests)
- [ ] Déploiement VPS (Nginx + systemd ou Docker Compose en production)

---

*Documentation générée par Claude Code — Mars 2026*
