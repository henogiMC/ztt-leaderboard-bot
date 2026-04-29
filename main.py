import asyncio
import json
import logging
import os
from logging.handlers import RotatingFileHandler

import discord
from discord.ext import commands

from db import init_pool


def _setup_logging() -> None:
    fmt = logging.Formatter("%(asctime)s [%(levelname)s] %(name)s: %(message)s")

    console = logging.StreamHandler()
    console.setFormatter(fmt)

    os.makedirs("logs", exist_ok=True)
    file_handler = RotatingFileHandler(
        "logs/bot.log",
        maxBytes=5 * 1024 * 1024,
        backupCount=7,
        encoding="utf-8",
    )
    file_handler.setFormatter(fmt)

    root = logging.getLogger()
    root.setLevel(logging.INFO)
    root.addHandler(console)
    root.addHandler(file_handler)

    logging.getLogger("discord.gateway").setLevel(logging.WARNING)
    logging.getLogger("discord.http").setLevel(logging.WARNING)
    logging.getLogger("discord.client").setLevel(logging.WARNING)


_setup_logging()
log = logging.getLogger(__name__)

with open("config.json") as _f:
    _cfg = json.load(_f)


class Bot(commands.Bot):
    def __init__(self) -> None:
        intents = discord.Intents.default()
        intents.members = (
            True  # needed to resolve guild membership for SHOW_FOREIGN_PLAYERS
        )
        super().__init__(
            command_prefix=commands.when_mentioned,
            intents=intents,
        )

    async def setup_hook(self) -> None:
        await init_pool()
        await self.load_extension("cogs.leaderboard")
        # Guild-scoped sync so the slash command appears instantly.
        await self.tree.sync(guild=discord.Object(id=_cfg["GUILD_ID"]))

    async def on_ready(self) -> None:
        print(f"Logged in as {self.user}  (ID: {self.user.id})")


async def main() -> None:
    async with Bot() as bot:
        await bot.start(os.environ["BOT_TOKEN"])


asyncio.run(main())
