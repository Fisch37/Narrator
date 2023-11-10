"""
This module provides a Singleton base class that allows subclassing.
"""
from typing import Self

class Singleton:
    """
    Superclass for singletons.
    Allows for patterns where a class only allows one instance of 
    itself. Attempting to construct a second instance will fail, 
    returning the old one.

    NOTE: This can always be circumvented using object.__new__
    """
    __OBJECT_DATA = {}

    def __new__(cls, *_args, **_kwargs) -> Self:
        try:
            return cls.__OBJECT_DATA[cls]
        except KeyError:
            return super().__new__(cls)
