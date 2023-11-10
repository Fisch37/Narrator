"""
Exposes a single function "setup_logging" that initialises the logger
for a 
"""
from logging import Formatter, StreamHandler
from logging.handlers import QueueHandler, QueueListener
from queue import Queue

from discord.utils import setup_logging as discord_logging, _ColourFormatter
from colorama.ansi import Fore, Style

DEFAULT_FORMATTER = "["+Fore.BLACK+"%(asctime)s {colour}%(levelname)-8s"\
    +Style.RESET_ALL+"] "+Style.BRIGHT+Fore.MAGENTA+"%(threadName)s@%(name)s: "\
    +Style.RESET_ALL+"%(message)s"

__all__ = (
    "setup_logging",
)

class _CustomFormatter(_ColourFormatter):
    FORMATS = {
        level: Formatter(
            DEFAULT_FORMATTER.format(colour=colour),
            '%Y-%m-%d %H:%M:%S',
        )
        for level, colour in _ColourFormatter.LEVEL_COLOURS
    }

def setup_logging(
        logging_level: str="INFO",
        formatter: Formatter=_CustomFormatter()
    ):
    """
    Initialises the default logger to use some relevant info.
    Uses a queue-based logger to avoid blocking behaviour in uncertain
    application scenarios.
    """
    queue = Queue(-1)
    queue_handler = QueueHandler(queue)
    stderr_handler = StreamHandler()
    stderr_handler.setFormatter(formatter)

    queue_listener = QueueListener(
        queue,
        stderr_handler
    )
    queue_listener.start()

    discord_logging(
        level=logging_level,
        formatter=None,
        handler=queue_handler
    )
