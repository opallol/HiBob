"""Async Postgres connection pool (asyncpg), created at app startup, closed at shutdown."""

from __future__ import annotations

import asyncpg

from hibob_core.config import settings

_pool: asyncpg.Pool | None = None


async def init_pool() -> asyncpg.Pool:
    global _pool
    if _pool is None:
        # asyncpg wants the scheme as postgresql:// (not postgresql+asyncpg://).
        _pool = await asyncpg.create_pool(settings.database_dsn, min_size=1, max_size=10)
    return _pool


async def close_pool() -> None:
    global _pool
    if _pool is not None:
        await _pool.close()
        _pool = None


def get_pool() -> asyncpg.Pool:
    if _pool is None:
        raise RuntimeError("DB pool not initialized; call init_pool() first.")
    return _pool
