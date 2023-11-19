"""
This module provides a Singleton base class that allows subclassing.
"""
from typing import TypeVar

Instance = TypeVar('Instance')


class SingletonMeta(type):
    """
    Metaclass for singletons.
    Typically the Singleton class should be used in favour of this.
    """
    __instance_cache = {}

    def __call__(cls: type[Instance], *args, **kwargs) -> Instance:
        if cls not in SingletonMeta.__instance_cache:
            SingletonMeta.__instance_cache[cls] = super().__call__(*args, **kwargs)
        return SingletonMeta.__instance_cache[cls]


class Singleton(metaclass=SingletonMeta):
    """
    Superclass for singletons.
    Allows for patterns where a class only allows one instance of
    itself. Attempting to construct a second instance will fail,
    returning the old one.

    NOTE: This can always be circumvented
    """
