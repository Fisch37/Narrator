from datetime import datetime, UTC
from threading import current_thread
from typing import NamedTuple, Self

EPOCH_START = datetime(2015, 1, 1, tzinfo=UTC)


class _SnowflakeRaw(NamedTuple):
    timestamp: int
    """Note that this is the "Discord Epoch", meaning the milliseconds since 2015"""
    worker_id: int
    process_id: int
    increment: int
    
    def to_int(self) -> int:
        return (
            self.timestamp << 22
            + self.worker_id << 17
            + self.process_id << 12
            + self.increment
        )
    
    @staticmethod
    def from_int(snowflake: int, /):
        return _SnowflakeRaw(
            snowflake >> 22,
            (snowflake & 0x3E0000) >> 17,
            (snowflake & 0x1F000) >> 12,
            snowflake & 0xFFF
        )
    
    @property
    def datetime(self) -> datetime:
        return datetime.fromtimestamp(
            self.timestamp/1000 + EPOCH_START.timestamp(),
            UTC
        )


class SnowflakeGenerator:
    def __init__(self, process_id: int|None=None):
        if process_id is None:
            # Impossible value for Discord to achieve
            process_id = 31
        self.process_id = process_id
        # ident would only ever be None if the threads isn't running.
        # It is running. It is currently executing this code.
        # FIXME: This may become problematic in multithreaded-applications as thread ids may collide
        self.worker_id: int = current_thread().ident & 0x1F # type: ignore
        self._increment = 0
    
    def generate_raw(self):
        time = datetime.now(UTC)
        discord_epoch = int(
            (time - EPOCH_START).total_seconds()
            * 1000
        )
        raw = _SnowflakeRaw(
            timestamp=discord_epoch,
            worker_id=self.worker_id,
            process_id=self.process_id,
            increment=self._increment
        )
        
        # Mod 4096 but in bit operations which is usually faster
        self._increment = (self._increment + 1) & 0xFFF
        
        return raw
    
    def generate(self) -> int:
        return self.generate_raw().to_int()
    
    def decompose(self, snowflake: int, /) -> _SnowflakeRaw:
        return _SnowflakeRaw.from_int(snowflake)
    
    # I'm not sure why anyone would ever use this
    def __next__(self) -> int:
        return self.generate()
    
    def __iter__(self) -> Self:
        return self


GENERATOR = SnowflakeGenerator()


def generate_snowflake() -> int:
    return GENERATOR.generate()