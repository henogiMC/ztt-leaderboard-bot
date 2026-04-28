import json
import logging

import discord
from discord import app_commands
from discord.ext import commands, tasks

from db import fetch_leaderboard
from embed import build_leaderboard_embed, build_page_embed

with open("config.json") as _f:
    _cfg = json.load(_f)

_PAGE_SIZE = 10

log = logging.getLogger(__name__)


# ── Paginated view ────────────────────────────────────────────────────────────
class LeaderboardView(discord.ui.View):
    def __init__(self, players: list[dict], page: int = 0) -> None:
        super().__init__(timeout=120)
        self.players = players
        self.page = page
        self.max_page = max(0, (len(players) - 1) // _PAGE_SIZE) if players else 0

    # ◀ previous
    @discord.ui.button(emoji="⬅️", style=discord.ButtonStyle.secondary)
    async def prev_page(
        self, interaction: discord.Interaction, button: discord.ui.Button
    ) -> None:
        if self.page > 0:
            self.page -= 1
        await interaction.response.edit_message(
            embed=build_page_embed(self.players, self.page), view=self
        )

    # ▶ next
    @discord.ui.button(emoji="➡️", style=discord.ButtonStyle.secondary)
    async def next_page(
        self, interaction: discord.Interaction, button: discord.ui.Button
    ) -> None:
        if self.page < self.max_page:
            self.page += 1
        await interaction.response.edit_message(
            embed=build_page_embed(self.players, self.page), view=self
        )


# ── Cog ───────────────────────────────────────────────────────────────────────
class LeaderboardCog(commands.Cog):
    def __init__(self, bot: commands.Bot) -> None:
        self.bot = bot
        self._msg_id: int | None = None  # cached ID of the channel embed message
        self.update_leaderboard.start()

    def cog_unload(self) -> None:
        self.update_leaderboard.cancel()

    # ── Hourly task ───────────────────────────────────────────────────────────
    @tasks.loop(hours=1)
    async def update_leaderboard(self) -> None:
        players = await fetch_leaderboard(
            _cfg["GAMEMODE"], _cfg["TIER_UNRANKED"], force=True
        )
        channel = self.bot.get_channel(_cfg["LEADERBOARD_CHANNEL_ID"])
        if channel is None:
            print("Leaderboard channel not found — check LEADERBOARD_CHANNEL_ID.")
            return

        embed = build_leaderboard_embed(players)

        # Try the cached message ID first to avoid a history scan every hour.
        if self._msg_id is not None:
            try:
                msg = await channel.fetch_message(self._msg_id)
                await msg.edit(embed=embed)
                return
            except discord.NotFound:
                self._msg_id = None  # message was deleted; fall through

        # Scan recent history for a previously sent bot message.
        async for msg in channel.history(limit=50):
            if msg.author == self.bot.user:
                self._msg_id = msg.id
                await msg.edit(embed=embed)
                return

        # No existing message — send a fresh one.
        sent = await channel.send(embed=embed)
        self._msg_id = sent.id

    @update_leaderboard.before_loop
    async def _before_loop(self) -> None:
        await self.bot.wait_until_ready()

    # ── Slash command ─────────────────────────────────────────────────────────
    @app_commands.command(name="leaderboard", description="Browse the full leaderboard")
    @app_commands.guilds(discord.Object(id=_cfg["GUILD_ID"]))
    async def leaderboard_cmd(self, interaction: discord.Interaction) -> None:
        players = await fetch_leaderboard(_cfg["GAMEMODE"], _cfg["TIER_UNRANKED"])
        await interaction.response.send_message(
            embed=build_page_embed(players, page=0),
            view=LeaderboardView(players),
            ephemeral=True,
        )


async def setup(bot: commands.Bot) -> None:
    await bot.add_cog(LeaderboardCog(bot))
