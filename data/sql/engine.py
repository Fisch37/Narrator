"""
Provides management functionality for the database.
Implements the AsyncDatabase singleton to allow easy management of the engine.
"""
from typing import Self
import logging
import sqlalchemy.ext.asyncio as asql

from util import Singleton
from data.sql.ormclasses import Base

LOGGER = logging.getLogger("Database")

class AsyncDatabase(Singleton):
    """
    Singleton for managing the database connection.
    Should be used with async-with statement to properly initialise the database api.
    Closes the engine after exiting the context manager.
    """
    def __init__(self, url: str):
        self._engine = asql.create_async_engine(url)
        self._sessionmaker = asql.async_sessionmaker(
            self.engine,
            expire_on_commit=False
        )

    @property
    def engine(self) -> asql.AsyncEngine:
        """
        Returns the underlying engine.
        (This should not be used when a sessionmaker is available)
        """
        return self._engine

    @property
    def sessionmaker(self) -> asql.async_sessionmaker:
        """
        Returns a callable that creates a new AsyncSession.
        """
        return self._sessionmaker

    async def __aenter__(self) -> Self:
        async with self.engine.begin() as connection:
            await connection.run_sync(Base.metadata.create_all)
        LOGGER.debug("Initialized database")

        return self

    async def __aexit__(self, exc_type, exc_value, traceback) -> None:
        await self.engine.dispose()
