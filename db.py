import logging
import os
import time
from typing import Optional

import asyncpg

log = logging.getLogger(__name__)

# ── Tier → points map ────────────────────────────────────────────────────────
TIER_POINTS: dict[str, int] = {
    "HT1": 60,
    "LT1": 45,
    "HT2": 30,
    "LT2": 20,
    "HT3": 10,
    "LT3": 6,
    "HT4": 4,
    "LT4": 3,
    "HT5": 2,
    "LT5": 1,
}

# ── Internal state ────────────────────────────────────────────────────────────
_pool: Optional[asyncpg.Pool] = None
_cache: Optional[list[dict]] = None
_cache_time: float = 0.0
_CACHE_TTL: float = 3600.0  # seconds — matches the hourly refresh loop


# ── Initialisation ────────────────────────────────────────────────────────────
async def init_pool() -> None:
    """Create the asyncpg connection pool. Call once at bot startup."""
    global _pool
    _pool = await asyncpg.create_pool(os.environ["DATABASE_URL"])


def _get_pool() -> asyncpg.Pool:
    if _pool is None:
        raise RuntimeError("Database pool not initialised — call init_pool() first.")
    return _pool


# ── Public API ────────────────────────────────────────────────────────────────
async def fetch_leaderboard(
    gamemode: str,
    tier_unranked: str,
    *,
    force: bool = False,
) -> list[dict]:
    """
    Return a sorted list of ranked players for *gamemode*.

    Each entry is::

        {
            "discord_id": str,
            "ign":        str,
            "tier":       str,   # e.g. "HT1"
            "points":     int,
        }

    Results are cached for CACHE_TTL seconds.  Pass ``force=True`` to bypass
    the cache and hit the database immediately (used by the hourly task loop).
    """
    global _cache, _cache_time

    now = time.monotonic()
    if not force and _cache is not None and (now - _cache_time) < _CACHE_TTL:
        return _cache

    async with _get_pool().acquire() as conn:
        rows = await conn.fetch(
            # Column names are double-quoted because gamemode names may contain spaces.
            f'SELECT discord_id, ign, "{gamemode}" AS tier '
            f"FROM players "
            f'WHERE "{gamemode}" IS NOT NULL AND "{gamemode}" != $1',
            tier_unranked,
        )

    players: list[dict] = []
    for row in rows:
        points = TIER_POINTS.get(row["tier"], 0)
        if points > 0:
            players.append(
                {
                    "discord_id": row["discord_id"],
                    "ign": row["ign"],
                    "tier": row["tier"],
                    "points": points,
                }
            )

    # Primary sort: points descending; secondary: discord_id for a stable order.
    players.sort(key=lambda p: (-p["points"], p["discord_id"]))

    _cache = players
    _cache_time = now
    return players
