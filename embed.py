from __future__ import annotations

import time
from typing import List, Tuple

import discord

from db import PlayerEntry

# Base points for non-retired tiers
TIER_POINTS = {
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


def compute_points(entry: PlayerEntry, show_retired: bool) -> float:
    tier = entry.tier
    base_points = TIER_POINTS.get(tier)
    if base_points is None:
        return 0.0

    if entry.is_retired and show_retired:
        return base_points / 2.0
    else:
        return float(base_points)


def sort_leaderboard(
    entries: List[PlayerEntry],
    show_retired: bool,
) -> List[Tuple[PlayerEntry, float]]:
    """
    Returns a list of (entry, points), sorted by points descending.
    Stable sort preserves DB order for ties.
    """
    scored = []
    for e in entries:
        pts = compute_points(e, show_retired)
        if pts <= 0:
            continue
        scored.append((e, pts))

    # Sort by points descending; stable sort keeps DB order for ties
    scored.sort(key=lambda x: x[1], reverse=True)
    return scored


def format_points(points: float) -> str:
    # Keep decimals but avoid trailing .0 when not needed
    if points.is_integer():
        return str(int(points))
    return f"{points}"


def build_leaderboard_lines(
    scored_entries: List[Tuple[PlayerEntry, float]],
    start_rank: int,
    end_rank: int,
    show_retired: bool,
) -> str:
    """
    Build the text lines for ranks [start_rank, end_rank] (1-based).
    """
    lines = []
    slice_entries = scored_entries[start_rank - 1 : end_rank]

    for idx, (entry, points) in enumerate(slice_entries, start=start_rank):
        mention = f"<@{entry.discord_id}>"
        tier_label = entry.tier
        if entry.is_retired and show_retired:
            tier_label = f"Retired {tier_label}"

        pts_str = format_points(points)

        if idx == 1:
            prefix = "🥇1st Place -"
        elif idx == 2:
            prefix = "🥈2nd Place -"
        elif idx == 3:
            prefix = "🥉3rd Place -"
        else:
            prefix = f"{idx}."

        if idx <= 3:
            line = f"{prefix} {mention} ({tier_label}): {pts_str}"
        else:
            line = f"{prefix} {mention} ({tier_label}): {pts_str}"

        lines.append(line)

    return "\n".join(lines) if lines else "No ranked players yet."


def build_leaderboard_embed(
    scored_entries: List[Tuple[PlayerEntry, float]],
    emoji_name: str,
    emoji_id: int,
    gamemode: str,
    show_retired: bool,
    page: int = 1,
    per_page: int = 10,
    live: bool = False,
) -> discord.Embed:
    """
    Build a leaderboard embed.
    - live=True: used for the locked channel (always page 1, top 10).
    - live=False: used for paginated /leaderboard.
    """
    total_entries = len(scored_entries)
    total_pages = max(1, (total_entries + per_page - 1) // per_page)

    if page < 1:
        page = 1
    if page > total_pages:
        page = total_pages

    start_rank = (page - 1) * per_page + 1
    end_rank = min(page * per_page, total_entries)

    emoji_str = f"<:{emoji_name}:{emoji_id}>"
    title = f"{emoji_str} {gamemode} Live Leaderboard {emoji_str}"

    description = build_leaderboard_lines(
        scored_entries,
        start_rank=start_rank,
        end_rank=end_rank,
        show_retired=show_retired,
    )

    embed = discord.Embed(
        title=title,
        description=description,
        color=discord.Color.gold(),
    )

    now = int(time.time())
    embed.set_footer(text=f"Last updated: <t:{now}:R>")

    if not live:
        embed.add_field(
            name="Page",
            value=f"{page}/{total_pages}",
            inline=False,
        )

    return embed
