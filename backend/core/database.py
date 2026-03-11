import asyncpg
import logging
from typing import Optional, Any
from contextlib import asynccontextmanager
from .config import get_settings

logger = logging.getLogger(__name__)

_pool: Optional[asyncpg.Pool] = None


async def init_db() -> None:
    """Initialize the connection pool."""
    global _pool
    settings = get_settings()
    _pool = await asyncpg.create_pool(
        dsn=settings.database_url,
        min_size=settings.db_pool_min,
        max_size=settings.db_pool_max,
        command_timeout=60,
    )
    logger.info("Database pool initialized")


async def close_db() -> None:
    """Close the connection pool."""
    global _pool
    if _pool:
        await _pool.close()
        _pool = None
        logger.info("Database pool closed")


def get_pool() -> asyncpg.Pool:
    if _pool is None:
        raise RuntimeError("Database pool not initialized. Call init_db() first.")
    return _pool


@asynccontextmanager
async def get_connection():
    """Context manager for a single connection."""
    pool = get_pool()
    async with pool.acquire() as conn:
        yield conn


async def fetch_one(query: str, *args) -> Optional[asyncpg.Record]:
    async with get_connection() as conn:
        return await conn.fetchrow(query, *args)


async def fetch_all(query: str, *args) -> list[asyncpg.Record]:
    async with get_connection() as conn:
        return await conn.fetch(query, *args)


async def execute(query: str, *args) -> str:
    async with get_connection() as conn:
        return await conn.execute(query, *args)


async def execute_many(query: str, args_list: list) -> None:
    async with get_connection() as conn:
        await conn.executemany(query, args_list)


async def get_config(key: str) -> Any:
    """Fetch a user config value by key."""
    row = await fetch_one(
        "SELECT value FROM user_config WHERE key = $1", key
    )
    return row["value"] if row else None


async def set_config(key: str, value: Any) -> None:
    """Upsert a user config value."""
    await execute(
        """
        INSERT INTO user_config (key, value, updated_at)
        VALUES ($1, $2, NOW())
        ON CONFLICT (key) DO UPDATE
          SET value = EXCLUDED.value,
              updated_at = NOW()
        """,
        key,
        value if isinstance(value, str) else str(value).replace("'", '"'),
    )
