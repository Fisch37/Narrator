from collections.abc import Iterable
from sqlalchemy.ext.mutable import MutableList

from util.limited_list import LimitedList

class FieldsList[T](LimitedList[T], MutableList):
    """Specialized version of LimitedList. Has a fixed size of 25"""
    def __init__(self, __iterable: Iterable[T] = (), /):
        super().__init__(__iterable, 25)
