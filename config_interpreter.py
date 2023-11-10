"""
API for the configuration file.
Exposes read_config and the Config TypedDict.
"""
import tomllib
from typing import TypedDict

class _DatabseConfig(TypedDict):
    dialect: str
    driver: str
    path: str

class Config(TypedDict):
    """
    Typing for the configuration object.
    """
    Database: _DatabseConfig


def read_config(path: str) -> Config:
    """
    Loads the configuration out of (path) as a dictionary.
    """
    with open(path,encoding="utf-8") as config_file:
        # Not using ConfigParser.read for better error detection
        return tomllib.load(config_file)
