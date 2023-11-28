"""
Exposes a single function "setup_logging" that initialises the logger.
This logger outputs into a queue and splits output into stdout and a log file.
"""
from logging import Formatter, StreamHandler, FileHandler
from logging.handlers import QueueHandler, QueueListener
from queue import Queue
from pathlib import Path
from sys import gettrace

from discord.utils import setup_logging as discord_logging, _ColourFormatter, utcnow
from colorama.ansi import Fore, Style

DEFAULT_FORMATTER = "[" + Fore.BLACK + "%(asctime)s {colour}%(levelname)-8s"\
    + Style.RESET_ALL + "] " + Style.BRIGHT + Fore.MAGENTA + "%(threadName)s@%(name)s: "\
    + Style.RESET_ALL + "%(message)s"

__all__ = (
    "setup_logging",
)


class _CustomColouredFormatter(_ColourFormatter):
    FORMATS = {
        level: Formatter(
            DEFAULT_FORMATTER.format(colour=colour),
            '%Y-%m-%d %H:%M:%S',
        )
        for level, colour in _ColourFormatter.LEVEL_COLOURS
    }


STDERR_FORMATTER = _CustomColouredFormatter()
FILE_FORMATTER = Formatter(
    "[%(asctime)s %(levelname)-8s] %(threadName)s@%(name)s: %(message)s"
)


def _is_debugging():
    """Checks if the program has an attached debugger"""
    return gettrace() is not None


def setup_logging(
        stderr_level: int|str=20,
        file_level: int|str=10,
        *,
        debug_stderr_level: int|str=10
):
    """
    Initialises the default logger to use some relevant info.
    Uses a queue-based logger to avoid blocking behaviour in uncertain
    application scenarios.
    """
    queue = Queue(-1)
    queue_handler = QueueHandler(queue)
    # Console Output (Coloured)
    stderr_handler = StreamHandler()
    stderr_handler.setFormatter(STDERR_FORMATTER)
    stderr_handler.setLevel(
        debug_stderr_level
        if _is_debugging()
        else stderr_level
    )
    # File Output
    filepath = Path("logs", utcnow().strftime("%Y-%m-%d+%H-%M-%S") + ".log")
    filepath.parent.mkdir(parents=True, exist_ok=True)
    file_handler = FileHandler(
        filepath,
        encoding="utf-8"
    )
    file_handler.setFormatter(FILE_FORMATTER)
    file_handler.setLevel(file_level)

    queue_listener = QueueListener(
        queue,
        stderr_handler,
        file_handler,
        respect_handler_level=True
    )
    queue_listener.start()

    discord_logging(
        level=0,
        formatter=None,  # type: ignore
        handler=queue_handler
    )
