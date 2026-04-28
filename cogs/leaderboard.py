from __future__ import annotations

import json
import os
import time
from typing import List, Optional, Tuple

import discord
from discord import app_commands
from discord.ext import commands

import db
from db import PlayerEntry
from embed import build_leaderboard_embed, sort_leaderboard

STATE_FILE = "leaderboard_state.json"


def load_state() -> dict:
    if not os.path.exists(STATE_FILE):
        return {}
    with open(STATE_FILE, "r", encoding="utf-8") as f:
        try:
            return json.load(f)
        except json.JSONDecodeError:
            return {}


def save_state(state: dict) -> None:
    with open(STATE_FILE, "w", encoding="utf-8") as f:
        json.dump(state, f)


class LeaderboardView(discord.ui.View):
    def __init__(
        self,
        scored_entries: List[Tuple[PlayerEntry, float]],
        emoji_name: str,
        emoji_id: int,
        gamemode: str,
        show_retired: bool,
        per_page: int = 10,
        timeout: Optional[float] = 120.0,
    ):
        super().__init__(timeout=timeout)
        self.scored_entries = scored_entries
        self.emoji_name = emoji_name
        self.emoji_id = emoji_id
        self.gamemode = gamemode
        self.show_retired = show_retired
        self.per_page = per_page
        self.page = 1

    async def update_message(self, interaction: discord.Interaction):
        embed = build_leaderboard_embed(
            self.scored_entries,
            emoji_name=self.emoji_name,
            emoji_id=self.emoji_id,
            gamemode=self.gamemode,
            show_retired=self.show_retired,
            page=self.page,
            per_page=self.per_page,
            live=False,
        )
        await interaction.response.edit_message(embed=embed, view=self)

    @discord.ui.button(emoji="◀️", style=discord.ButtonStyle.secondary)
    async def previous_page(
        self,
        interaction: discord.Interaction,
        button: discord.ui.Button,
    ):
        total_entries = len(self.scored_entries)
        total_pages = max(1, (total_entries + self.per_page - 1) // self.per_page)

        if self.page > 1:
            self.page -= 1
        else:
            self.page = total_pages

        await self.update_message(interaction)

    @discord.ui.button(emoji="▶️", style=discord.ButtonStyle.secondary)
    async def next_page(
        self,
        interaction: discord.Interaction,
        button: discord.ui.Button,
    ):
        total_entries = len(self.scored_entries)
        total_pages = max(1, (total_entries + self.per_page - 1) // self.per_page)

        if self.page < total_pages:
            self.page += 1
        else:
            self.page = 1

        await self.update_message(interaction)


class LeaderboardCog(commands.Cog):
    def __init__(self, bot: commands.Bot):
        self.bot = bot
        self.config = bot.config  # type: ignore[attr-defined]

        self.guild_id: int = self.config["GUILD_ID"]
        self.channel_id: int = self.config["LEADERBOARD_CHANNEL_ID"]
        self.emoji_name: str = self.config["LEADERBOARD_EMOJI_NAME"]
        self.emoji_id: int = self.config["LEADERBOARD_EMOJI_ID"]
        self.gamemode: str = self.config["GAMEMODE"]
        self.tier_unranked: str = self.config["TIER_UNRANKED"]
        self.show_retired: bool = self.config["SHOW_RETIRED_PLAYERS"]

        self._cached_scored_entries: List[Tuple[PlayerEntry, float]] = []

        # Start background task
        self.bot.loop.create_task(self.leaderboard_loop())

    async def cog_unload(self):
        # Nothing special, but if we had tasks we'd cancel them here.
        pass

    async def fetch_and_score_leaderboard(self) -> List[Tuple[PlayerEntry, float]]:
        entries = await db.get_all_players_for_gamemode(
            include_retired=self.show_retired
        )
        scored = sort_leaderboard(entries, show_retired=self.show_retired)
        self._cached_scored_entries = scored
        return scored

    async def get_or_create_leaderboard_message(
        self, channel: discord.TextChannel
    ) -> discord.Message:
        state = load_state()
        message_id = state.get("message_id")

        if message_id:
            try:
                msg = await channel.fetch_message(message_id)
                return msg
            except (discord.NotFound, discord.Forbidden, discord.HTTPException):
                # Message missing or inaccessible; we'll recreate it.
                pass

        # Create a new message
        if not self._cached_scored_entries:
            scored = await self.fetch_and_score_leaderboard()
        else:
            scored = self._cached_scored_entries

        embed = build_leaderboard_embed(
            scored,
            emoji_name=self.emoji_name,
            emoji_id=self.emoji_id,
            gamemode=self.gamemode,
            show_retired=self.show_retired,
            page=1,
            per_page=10,
            live=True,
        )
        msg = await channel.send(embed=embed)

        state["message_id"] = msg.id
        save_state(state)

        return msg

    async def update_leaderboard_message(self):
        guild = self.bot.get_guild(self.guild_id)
        if guild is None:
            return

        channel = guild.get_channel(self.channel_id)
        if not isinstance(channel, discord.TextChannel):
            return

        scored = await self.fetch_and_score_leaderboard()
        msg = await self.get_or_create_leaderboard_message(channel)

        embed = build_leaderboard_embed(
            scored,
            emoji_name=self.emoji_name,
            emoji_id=self.emoji_id,
            gamemode=self.gamemode,
            show_retired=self.show_retired,
            page=1,
            per_page=10,
            live=True,
        )

        try:
            await msg.edit(embed=embed)
        except (discord.Forbidden, discord.HTTPException):
            # If editing fails, we could try recreating, but for now we just swallow.
            pass

    async def leaderboard_loop(self):
        await self.bot.wait_until_ready()
        while not self.bot.is_closed():
            # Align to next full UTC hour
            now = time.time()
            seconds_in_hour = 3600
            sleep_seconds = seconds_in_hour - (int(now) % seconds_in_hour)

            # Sleep until the next hour
            await discord.utils.sleep_until(
                discord.utils.utcnow().replace(minute=0, second=0, microsecond=0)
                + discord.utils.timedelta(seconds=sleep_seconds)
            )

            # After waking up, update leaderboard
            try:
                await self.update_leaderboard_message()
            except Exception as e:
                print(f"Error updating leaderboard: {e}")

    @app_commands.command(
        name="leaderboard",
        description="Show the leaderboard for the configured gamemode.",
    )
    async def leaderboard_command(self, interaction: discord.Interaction):
        # Use cached data if available; otherwise fetch fresh.
        if not self._cached_scored_entries:
            scored = await self.fetch_and_score_leaderboard()
        else:
            scored = self._cached_scored_entries

        embed = build_leaderboard_embed(
            scored,
            emoji_name=self.emoji_name,
            emoji_id=self.emoji_id,
            gamemode=self.gamemode,
            show_retired=self.show_retired,
            page=1,
            per_page=10,
            live=False,
        )

        view = LeaderboardView(
            scored_entries=scored,
            emoji_name=self.emoji_name,
            emoji_id=self.emoji_id,
            gamemode=self.gamemode,
            show_retired=self.show_retired,
            per_page=10,
        )

        await interaction.response.send_message(
            embed=embed,
            view=view,
            ephemeral=True,
        )
