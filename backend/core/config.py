from pydantic_settings import BaseSettings
from pydantic import Field
from functools import lru_cache
from typing import List


class Settings(BaseSettings):
    # App
    app_name: str = "PULSE"
    app_version: str = "0.1.0"
    debug: bool = False

    # Database
    database_url: str = Field(
        default="postgresql://localhost:5432/pulse",
        env="DATABASE_URL"
    )
    db_pool_min: int = 2
    db_pool_max: int = 10

    # Anthropic
    anthropic_api_key: str = Field(default="", env="ANTHROPIC_API_KEY")
    claude_model: str = "claude-sonnet-4-5"
    claude_max_tokens: int = 2000

    # CCXT / Exchanges
    exchange_id: str = "binance"
    # Sandbox OFF: public market data (prices) doesn't require an API key.
    # Binance sandbox doesn't support fetch_ticker anyway.
    ccxt_sandbox: bool = False

    # Scheduler
    price_fetch_interval_minutes: int = 5
    rss_fetch_interval_minutes: int = 15
    morning_digest_hour: int = 8
    evening_digest_hour: int = 18

    # News
    news_relevance_threshold: float = 0.7
    news_batch_size: int = 20

    # Portfolio
    rebalance_drift_threshold: float = 5.0  # percent

    # CORS
    allowed_origins: List[str] = ["http://localhost:5173", "http://localhost:3000"]

    class Config:
        env_file = ".env"
        env_file_encoding = "utf-8"
        case_sensitive = False


@lru_cache()
def get_settings() -> Settings:
    return Settings()
