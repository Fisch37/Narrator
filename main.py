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

TOKEN_PATH = "token"
CONFIG_PATH = "config.cfg"
EXTENSIONS = (

)

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
        logging.error('The token file "%s" does not exist!',TOKEN_PATH)
        exit(102)

    token = path.read_text("utf-8")\
        .strip()

    if len(token) == 0:
        logging.error("No token is set!")
        exit(101)

    return token

setup_logging()
intents = discord.Intents.default()
bot = commands.Bot("/",intents=intents)
config = read_config(CONFIG_PATH)

@bot.event
async def on_ready():
    """Called when the bot is ready to interact with the world."""
    logging.info("Logged in as %s!",bot.user)

async def main():
    """Main executing function of the bot"""
    async with bot:
        async with asyncio.TaskGroup() as tg:
            for extension in EXTENSIONS:
                tg.create_task(
                    bot.load_extension(extension),
                    name=f"Loading Extension {extension}"
                )

        await bot.start(read_token())

asyncio.run(main())
