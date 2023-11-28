"""
Main executing file for this discord bot.
Has the task of starting the bot and loading all extensions.
"""
import logging
import asyncio
from pathlib import Path

import discord
from discord.ext import commands

from logger_setup import setup_logging
from config_interpreter import read_config
from data import AsyncDatabase
from translation_file_manager import FileSourcedTranslation

TOKEN_PATH = "token"
CONFIG_PATH = "config.toml"
EXTENSIONS = (
    "extensions.masks",
)


class CustomBot(commands.Bot):
    async def setup_hook(self) -> None:
        await self.tree.set_translator(FileSourcedTranslation(config["Bot"]["translations"]))

        guild_id: int = config["Bot"]["debug_guild"]
        guild = discord.Object(guild_id) if guild_id > 0 else None
        if guild is not None:
            logging.info("Debug guild is enabled! Set to %d", guild_id)
            self.tree.copy_global_to(guild=guild)
        await self.tree.sync(guild=guild)
        await self.tree.fetch_commands(guild=guild)
        logging.info("Synced commands!")
        return await super().setup_hook()


def read_token():
    """
    Reads in the bot token from the file specified in TOKEN_PATH
    and returns it.
    Exits the program if the token file doesn't exist or is invalid.
    """
    path = Path(
        Path(__file__).parent,
        TOKEN_PATH
    )
    if not path.exists():
        logging.error('The token file "%s" does not exist!', TOKEN_PATH)
        exit(102)
    token = path.read_text("utf-8")\
        .strip()
    if len(token) == 0:
        logging.error("No token is set!")
        exit(101)
    return token


setup_logging()
intents = discord.Intents.default()
bot = CustomBot("/", intents=intents)
config = read_config(CONFIG_PATH)


async def load_extension_task(extension: str):
    """
    Loads an extension surrounded by adequate logging.
    Also safely logs a failed extension load
    """
    try:
        await bot.load_extension(extension)
    except commands.ExtensionError as e:
        logging.error("Failed to load extension %s! (%s)", extension, e)
        logging.debug(e, exc_info=True)
    else:
        logging.info("Loaded extension %s", extension)


@bot.event
async def on_ready():
    """Called when the bot is ready to interact with the world."""
    logging.info("Logged in as %s!", bot.user)


async def main():
    """Main executing function of the bot"""
    async with bot, AsyncDatabase(config["Database"]["url"]):
        async with asyncio.TaskGroup() as tg:
            for extension in EXTENSIONS:
                tg.create_task(
                    load_extension_task(extension),
                    name=f"Loading Extension {extension}"
                )

        await bot.start(read_token())

asyncio.run(main())
