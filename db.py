from __future__ import annotations

from dataclasses import dataclass
from typing import Dict, List, Optional

import asyncpg

_pool: Optional[asyncpg.Pool] = None
_GAMEMODE: str = "Mace"
_TIER_UNRANKED: str = "Unranked"


@dataclass
class PlayerEntry:
    discord_id: str
    ign: str
    tier: str
    is_retired: bool


async def init_db(database_url: str, gamemode: str, tier_unranked: str) -> None:
    global _pool, _GAMEMODE, _TIER_UNRANKED
    _GAMEMODE = gamemode
    _TIER_UNRANKED = tier_unranked
    _pool = await asyncpg.create_pool(database_url)


def _get_pool() -> asyncpg.Pool:
    if _pool is None:
        raise RuntimeError("Database pool not initialized. Call init_db first.")
    return _pool


async def get_all_players_for_gamemode(include_retired: bool) -> List[PlayerEntry]:
    """
    Fetch all players for the configured gamemode, optionally including retired players.
    - Non-unranked players from `players` table.
    - Active retirements from `retirements` table (if include_retired).
    """
    pool = _get_pool()
    gamemode = _GAMEMODE
    tier_unranked = _TIER_UNRANKED

    players: Dict[str, PlayerEntry] = {}

    # Fetch non-unranked players for this gamemode
    # Column name is quoted because it may contain spaces.
    async with pool.acquire() as conn:
        rows = await conn.fetch(
            f"""
            SELECT discord_id, ign, "{gamemode}" AS tier
            FROM players
            WHERE "{gamemode}" IS NOT NULL
              AND "{gamemode}" != $1
            """,
            tier_unranked,
        )

    for row in rows:
        discord_id = row["discord_id"]
        ign = row["ign"]
        tier = row["tier"]
        if not tier or tier == tier_unranked:
            continue
        players[discord_id] = PlayerEntry(
            discord_id=discord_id,
            ign=ign,
            tier=tier,
            is_retired=False,
        )

    if not include_retired:
        return list(players.values())

    # Fetch active retirements for this gamemode and join with players to get ign
    async with pool.acquire() as conn:
        rows_retired = await conn.fetch(
            """
            SELECT r.discord_id, r.tier, p.ign
            FROM retirements r
            JOIN players p ON p.discord_id = r.discord_id
            WHERE r.gamemode = $1
              AND r.unretired_at IS NULL
            """,
            gamemode,
        )

    for row in rows_retired:
        discord_id = row["discord_id"]
        ign = row["ign"]
        tier = row["tier"]

        # Normalize tier: if it already starts with "Retired ", strip it for scoring
        # but we keep is_retired=True and will add "Retired " in display.
        if isinstance(tier, str) and tier.startswith("Retired "):
            base_tier = tier[len("Retired ") :]
        else:
            base_tier = tier

        # If player already exists as non-retired, retired takes precedence when SHOW_RETIRED_PLAYERS is true.
        players[discord_id] = PlayerEntry(
            discord_id=discord_id,
            ign=ign,
            tier=base_tier,
            is_retired=True,
        )

    return list(players.values())
