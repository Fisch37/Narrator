"""
This module provides a Singleton base class that allows subclassing.
"""
from typing import Self

class SingletonMeta(type):
    """
    Metaclass for singletons.
    Typically the Singleton class should be used in favour of this.
    """
    __instance_cache = {}

    def __call__(cls, *args, **kwargs) -> Self:
        if cls not in cls.__instance_cache:
            cls.__instance_cache[cls] = super().__call__(*args,**kwargs)
        return cls.__instance_cache[cls]

class Singleton(metaclass=SingletonMeta):
    """
    Superclass for singletons.
    Allows for patterns where a class only allows one instance of 
    itself. Attempting to construct a second instance will fail, 
    returning the old one.

    NOTE: This can always be circumvented
    """
