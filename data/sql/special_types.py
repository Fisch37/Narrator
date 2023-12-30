from collections.abc import Iterable
from sqlalchemy.ext.orderinglist import OrderingList

from util.limited_list import LimitedList

class FieldsList[T](LimitedList[T], OrderingList):
    """Specialized version of LimitedList. Has a fixed size of 25"""
    def __init__(self, __iterable: Iterable[T] = (), /):
        super().__init__(__iterable, 25)
