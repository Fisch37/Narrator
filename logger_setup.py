"""
Exposes a single function "setup_logging" that initialises the logger
for a 
"""
# from queue import Queue
# from logging.handlers import QueueHandler, QueueListener
# from logging import getLogger, StreamHandler, Formatter

from discord.utils import setup_logging as discord_logging

# NOTE: This is unused
# DEFAULT_LOGGING_FORMAT = "[%(asctime)s | %(name)s, %(threadName)s \
# ] %(levelname)s: %(msg)s"

__all__ = (
    "setup_logging",
)

def setup_logging(
        logging_level: str="INFO"
    ):
    """
    Initialises the default logger to use some relevant info.
    Uses a queue-based logger to avoid blocking behaviour in uncertain
    application scenarios.
    """
    # TODO: Find some way to implement this with a Queue to avoid blocking behaviour

    discord_logging(
        level=logging_level
    )
