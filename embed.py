import json
import logging

import discord

with open("config.json") as _f:
    _cfg = json.load(_f)

_EMOJI = f"<:{_cfg['LEADERBOARD_EMOJI_NAME']}:{_cfg['LEADERBOARD_EMOJI_ID']}>"
_GAMEMODE = _cfg["GAMEMODE"]
_PAGE_SIZE = 10

log = logging.getLogger(__name__)


# ── Helpers ───────────────────────────────────────────────────────────────────
def _format_line(rank: int, player: dict) -> str:
    mention = f"<@{player['discord_id']}>"
    tier = player["tier"]
    points = player["points"]
    match rank:
        case 1:
            return f"🥇 1st Place — {mention} ({tier}): {points}"
        case 2:
            return f"🥈 2nd Place — {mention} ({tier}): {points}"
        case 3:
            return f"🥉 3rd Place — {mention} ({tier}): {points}"
        case _:
            return f"{rank}. {mention} ({tier}): {points}"


def _base_embed(lines: list[str], footer: str | None = None) -> discord.Embed:
    title = f"{_EMOJI} {_GAMEMODE} Live Leaderboard {_EMOJI}"
    embed = discord.Embed(
        title=title,
        description="\n".join(lines) if lines else "No ranked players yet.",
        color=0xFFD700,
    )
    if footer:
        embed.set_footer(text=footer)
    return embed


# ── Public builders ───────────────────────────────────────────────────────────
def build_leaderboard_embed(players: list[dict]) -> discord.Embed:
    """Top-10 embed kept in the locked leaderboard channel."""
    lines = [_format_line(i + 1, p) for i, p in enumerate(players[:_PAGE_SIZE])]
    return _base_embed(lines)


def build_page_embed(players: list[dict], page: int) -> discord.Embed:
    """Paginated embed returned by the /leaderboard slash command."""
    start = page * _PAGE_SIZE
    chunk = players[start : start + _PAGE_SIZE]
    lines = [_format_line(start + i + 1, p) for i, p in enumerate(chunk)]

    total_pages = max(1, -(-len(players) // _PAGE_SIZE))  # ceiling division
    footer = f"Page {page + 1}/{total_pages}  •  {len(players)} ranked players"
    return _base_embed(lines, footer=footer)
