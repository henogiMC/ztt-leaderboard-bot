import asyncio
import json
import os

import discord
from discord.ext import commands

import db
from cogs.leaderboard import LeaderboardCog


def load_config(path: str = "config.json") -> dict:
    with open(path, "r", encoding="utf-8") as f:
        return json.load(f)


async def main():
    config = load_config()

    token = os.getenv("BOT_TOKEN")
    database_url = os.getenv("DATABASE_URL")

    if not token:
        raise RuntimeError("BOT_TOKEN environment variable is not set.")
    if not database_url:
        raise RuntimeError("DATABASE_URL environment variable is not set.")

    intents = discord.Intents.default()
    # We don't strictly need privileged intents for this use case.
    bot = commands.Bot(command_prefix="!", intents=intents)

    # Attach config to bot for easy access in cogs
    bot.config = config  # type: ignore[attr-defined]

    # Initialize DB pool
    await db.init_db(database_url, config["GAMEMODE"], config["TIER_UNRANKED"])

    @bot.event
    async def on_ready():
        print(f"Logged in as {bot.user} (ID: {bot.user.id})")
        print("------")

        # Sync commands to the configured guild
        guild_id = config["GUILD_ID"]
        guild = discord.Object(id=guild_id)
        bot.tree.copy_global_to(guild=guild)
        await bot.tree.sync(guild=guild)
        print(f"Synced commands to guild {guild_id}")

    # Add leaderboard cog
    await bot.add_cog(LeaderboardCog(bot))

    await bot.start(token)


if __name__ == "__main__":
    asyncio.run(main())
