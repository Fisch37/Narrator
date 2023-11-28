"""
API for the configuration file.
Exposes read_config and the Config TypedDict.
"""
import tomllib
from typing import TypedDict


class _DatabaseConfig(TypedDict):
    url: str


class _BotConfig(TypedDict):
    debug_guild: int


class Config(TypedDict):
    """
    Typing for the configuration object.
    """
    Database: _DatabaseConfig
    Bot: _BotConfig


def read_config(path: str) -> Config:
    """
    Loads the configuration out of (path) as a dictionary.
    """
    with open(path, "rb") as config_file:
        # Not using ConfigParser.read for better error detection
        return tomllib.load(config_file)  # type: ignore
