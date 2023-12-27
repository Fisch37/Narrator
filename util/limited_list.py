"""Implements the LimitedList class, allowing for bounded lists."""
from collections.abc import Iterable, Collection
from typing import TypeVar

T = TypeVar('T')


class LimitedList(list[T]):
    """Mutable sequence with an upper bound on its size."""
    __slots__ = ("_size",)

    def __init__(
            self,
            __iterable: Iterable[T]=(),
            /,
            size: int=-1
    ):
        super().__init__(__iterable)
        self._size = size

    def append(self, __object: T) -> None:
        if len(self) >= self._size:
            raise RuntimeError("List is full")
        super().append(__object)

    def extend(self, __iterable: Iterable[T]) -> None:
        for e in __iterable:
            self.append(e)

    def extend_safely(self, __iterable: Collection[T]) -> None:
        """
        Extend list by __iterable or raise RuntimeError if extension
        would go out-of-bounds.
        """
        if len(self) + len(__iterable) <= self.size:
            raise RuntimeError("Extending would go out-of-bounds")
        super().extend(__iterable)

    @property
    def size(self) -> int:
        """
        The maximum legal size of the list. This is not necessarily
        the current length.
        """
        return self._size

    def __repr__(self) -> str:
        return f"LimitedList({self.size}@{list.__repr__(self)})"
