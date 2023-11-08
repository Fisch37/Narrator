"""
Exposes a single function "setup_logging" that initialises the logger
for a 
"""
from queue import Queue
from logging.handlers import QueueHandler, QueueListener
from logging import getLogger, StreamHandler, Formatter

DEFAULT_LOGGING_FORMAT = "[%(asctime)s | %(name)s, %(threadName)s \
] %(levelname)s: %(msg)s"

__all__ = (
    "setup_logging",
)

def setup_logging(
        logging_level: str="INFO",
        logging_format: str=DEFAULT_LOGGING_FORMAT
    ):
    """
    Initialises the default logger to use some relevant info.
    Uses a queue-based logger to avoid blocking behaviour in uncertain
    application scenarios.
    """
    que = Queue()
    queue_handler = QueueHandler(que)
    handler = StreamHandler()
    listener = QueueListener(que, handler)

    root = getLogger()
    root.setLevel(logging_level)
    root.addHandler(queue_handler)
    handler.setFormatter(
        Formatter(logging_format)
    )
    listener.start()
