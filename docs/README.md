# PULSE - Personal Intelligence Operating System

> Finance + News, orchestrated by Claude AI. Deploy in one command.

## Quickstart (NixOS)

```bash
# 1. Clone
git clone https://github.com/pulse-os/pulse
cd pulse

# 2. Enter dev environment
nix develop

# 3. Configure
cp .env.example .env
# Edit .env: add ANTHROPIC_API_KEY

# 4. Init database
createdb pulse
psql -d pulse -f database/schema.sql

# 5. Start backend
uvicorn backend.main:app --reload

# 6. Start frontend (new terminal)
cd frontend && npm install && npm run dev
```

Open http://localhost:5173

## Architecture

```
PULSE
├── FinPulse    BTC/ETH/PAXG portfolio tracking + DCA backtest
├── NewsPulse   10 RSS feeds filtered by Claude AI
└── Claude Chat Context-aware Q&A with portfolio + news data
```

## Stack

| Layer    | Tech                              |
|----------|-----------------------------------|
| Backend  | Python 3.11, FastAPI, Anthropic   |
| Frontend | React 18, TypeScript, TailwindCSS |
| DB       | TimescaleDB (PostgreSQL)          |
| Infra    | NixOS, systemd, nginx             |

## Environment Variables

| Key                | Required | Description              |
|--------------------|----------|--------------------------|
| ANTHROPIC_API_KEY  | Yes      | Claude API key           |
| DATABASE_URL       | No       | Defaults to localhost    |
| CCXT_SANDBOX       | No       | Use exchange sandbox     |

## API Endpoints

See http://localhost:8000/docs (Swagger) when running.

Key endpoints:
- `GET /api/portfolio` - Current positions
- `GET /api/portfolio/insight` - Claude daily brief
- `GET /api/news` - Filtered articles
- `GET /api/news/digest/{morning|evening}` - AI digest
- `POST /api/chat` - Claude chat
- `POST /api/dca/backtest` - DCA simulation
- `WS /ws` - Live updates
