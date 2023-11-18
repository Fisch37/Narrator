"""
Provides something called TypeDecorators, which serve
as middleware between the database and python.
In more complicated code layouts these allow for custom
logic to transform column data into a python object.

Also provides type aliases to allow easier use of these type decorators
"""

from typing import Annotated, Any
from sqlalchemy.engine.interfaces import Dialect
import sqlalchemy.types as types

Snowflake = Annotated[int, "Snowflake"]


class HugeInt(types.TypeDecorator[int]):
    """
    Used for storing integers that are expected to be too large for the database.
    This will usually be the case for snowflakes.
    """

    impl = types.String
    cache_ok = True

    def process_bind_param(self, value: int | None, dialect: Dialect) -> Any:
        """Converts the value stored back into a string for the database"""
        return str(value) if value is not None else None
    
    def process_result_value(self, value: Any | None, dialect: Dialect) -> int | None:
        """Converts the received string into the integer it represents"""
        return int(value) if value is not None else None
    
    def process_literal_param(self, value: int | None, dialect: Dialect) -> str:
        return super().process_literal_param(value, dialect)
    
    @property
    def python_type(self) -> type[int]:
        return int
