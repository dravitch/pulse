-- PULSE Database Schema
-- Requires TimescaleDB extension

CREATE EXTENSION IF NOT EXISTS timescaledb CASCADE;

-- ─── TIME-SERIES TABLES ────────────────────────────────────────────────────

-- Market prices (BTC, ETH, PAXG)
CREATE TABLE IF NOT EXISTS market_prices (
    time        TIMESTAMPTZ NOT NULL,
    symbol      TEXT        NOT NULL,
    price       NUMERIC(18, 8) NOT NULL,
    volume_24h  NUMERIC(18, 2),
    PRIMARY KEY (time, symbol)
);

SELECT create_hypertable('market_prices', 'time', if_not_exists => TRUE);

-- Portfolio snapshots
CREATE TABLE IF NOT EXISTS portfolio_positions (
    time            TIMESTAMPTZ NOT NULL,
    asset           TEXT        NOT NULL,
    units           NUMERIC(18, 8) NOT NULL,
    avg_cost_basis  NUMERIC(18, 8) NOT NULL,
    current_value   NUMERIC(18, 2) NOT NULL,
    PRIMARY KEY (time, asset)
);

SELECT create_hypertable('portfolio_positions', 'time', if_not_exists => TRUE);

-- ─── TRANSACTIONAL TABLES ─────────────────────────────────────────────────

-- DCA transactions
CREATE TABLE IF NOT EXISTS dca_transactions (
    id               SERIAL PRIMARY KEY,
    time             TIMESTAMPTZ NOT NULL DEFAULT NOW(),
    asset            TEXT        NOT NULL,
    units            NUMERIC(18, 8) NOT NULL,
    price            NUMERIC(18, 8) NOT NULL,
    amount_usd       NUMERIC(18, 2) NOT NULL,
    fees             NUMERIC(18, 2),
    transaction_type TEXT        NOT NULL CHECK (transaction_type IN ('BUY', 'SELL', 'SIMULATED'))
);

-- Trading signals
CREATE TABLE IF NOT EXISTS signals (
    id           SERIAL PRIMARY KEY,
    time         TIMESTAMPTZ NOT NULL DEFAULT NOW(),
    signal_type  TEXT        NOT NULL,
    asset        TEXT,
    confidence   NUMERIC(3, 2) CHECK (confidence >= 0 AND confidence <= 1),
    data         JSONB,
    actioned     BOOLEAN DEFAULT FALSE
);

-- RSS articles
CREATE TABLE IF NOT EXISTS rss_articles (
    id              SERIAL PRIMARY KEY,
    fetched_at      TIMESTAMPTZ NOT NULL DEFAULT NOW(),
    source          TEXT        NOT NULL,
    title           TEXT        NOT NULL,
    url             TEXT UNIQUE NOT NULL,
    published       TIMESTAMPTZ,
    content         TEXT,
    relevance_score NUMERIC(3, 2) CHECK (relevance_score >= 0 AND relevance_score <= 1),
    read            BOOLEAN DEFAULT FALSE,
    archived        BOOLEAN DEFAULT FALSE,
    summary         TEXT
);

-- User configuration
CREATE TABLE IF NOT EXISTS user_config (
    key        TEXT PRIMARY KEY,
    value      JSONB NOT NULL,
    updated_at TIMESTAMPTZ NOT NULL DEFAULT NOW()
);

-- ─── INDEXES ───────────────────────────────────────────────────────────────

CREATE INDEX IF NOT EXISTS idx_market_prices_symbol ON market_prices (symbol, time DESC);
CREATE INDEX IF NOT EXISTS idx_signals_type ON signals (signal_type, time DESC);
CREATE INDEX IF NOT EXISTS idx_signals_unactioned ON signals (actioned, time DESC) WHERE actioned = FALSE;
CREATE INDEX IF NOT EXISTS idx_articles_unread ON rss_articles (read, fetched_at DESC) WHERE read = FALSE;
CREATE INDEX IF NOT EXISTS idx_articles_relevance ON rss_articles (relevance_score DESC) WHERE relevance_score IS NOT NULL;
CREATE INDEX IF NOT EXISTS idx_dca_asset ON dca_transactions (asset, time DESC);

-- ─── DEFAULT CONFIG ────────────────────────────────────────────────────────

INSERT INTO user_config (key, value) VALUES
    ('portfolio_targets', '{"BTC": 60, "ETH": 30, "PAXG": 10}'),
    ('dca_config', '{"monthly_amount": 500, "periods": 60, "assets": ["BTC", "ETH"]}'),
    ('news_interests', '["bitcoin", "ethereum", "crypto", "AI", "technology"]'),
    ('rss_feeds', '[
        {"name": "Hacker News", "url": "https://news.ycombinator.com/rss"},
        {"name": "CoinDesk", "url": "https://www.coindesk.com/arc/outboundfeeds/rss/"},
        {"name": "TechCrunch", "url": "https://techcrunch.com/feed/"},
        {"name": "The Block", "url": "https://www.theblock.co/rss.xml"},
        {"name": "Decrypt", "url": "https://decrypt.co/feed"},
        {"name": "CoinTelegraph", "url": "https://cointelegraph.com/rss"},
        {"name": "Bitcoin Magazine", "url": "https://bitcoinmagazine.com/.rss/full/"},
        {"name": "Ars Technica", "url": "https://feeds.arstechnica.com/arstechnica/index"},
        {"name": "MIT Tech Review", "url": "https://www.technologyreview.com/feed/"},
        {"name": "Wired", "url": "https://www.wired.com/feed/rss"}
    ]'),
    ('digest_schedule', '{"morning_hour": 8, "evening_hour": 18}'),
    ('rebalance_threshold', '5.0')
ON CONFLICT (key) DO NOTHING;

-- ─── CONTINUOUS AGGREGATES (TimescaleDB) ──────────────────────────────────

-- Daily OHLCV for market prices
CREATE MATERIALIZED VIEW IF NOT EXISTS market_prices_daily
WITH (timescaledb.continuous) AS
SELECT
    time_bucket('1 day', time) AS bucket,
    symbol,
    first(price, time) AS open,
    max(price)         AS high,
    min(price)         AS low,
    last(price, time)  AS close,
    avg(price)         AS avg_price
FROM market_prices
GROUP BY bucket, symbol
WITH NO DATA;
