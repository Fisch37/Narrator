"""
Provides management functionality for the database.
Implements the AsyncDatabase singleton to allow easy management of the engine.
"""
from typing import Self
import logging
import sqlalchemy.ext.asyncio as asql
from sqlalchemy.orm import DeclarativeBase, MappedAsDataclass
from data.sql.type_decorators import HugeInt, Snowflake

from util import Singleton

LOGGER = logging.getLogger("data.sql.engine")


class Base(MappedAsDataclass, asql.AsyncAttrs, DeclarativeBase):
    """Base class for declarative SQL classes found below."""
    type_annotation_map = {
        Snowflake: HugeInt
    }


class AsyncDatabase(Singleton):
    """
    Singleton for managing the database connection.
    Should be used with async-with statement to properly initialise the database api.
    Closes the engine after exiting the context manager.
    """
    def __init__(self, url: str|None=None):
        if url is None:
            raise RuntimeError("First-time constructor must specify url argument")
        self._engine = asql.create_async_engine(url, echo=False)
        self._sessionmaker = asql.async_sessionmaker(
            self.engine,
            expire_on_commit=False
        )
        self._opened = True

    @property
    def engine(self) -> asql.AsyncEngine:
        """
        Returns the underlying engine.
        (This should not be used when a sessionmaker is available)
        """
        return self._engine

    @property
    def sessionmaker(self) -> asql.async_sessionmaker[asql.AsyncSession]:
        """
        Returns a callable that creates a new AsyncSession.
        """
        return self._sessionmaker

    @property
    def is_opened(self) -> bool:
        """
        Returns whether or not the engine is currently open or not.
        """
        return self._opened

    async def __aenter__(self) -> Self:
        import data.sql.ormclasses  # Forces ormclasses to be loaded, creating the ORM
        async with self.engine.begin() as connection:
            await connection.run_sync(Base.metadata.create_all)
        LOGGER.debug("Initialized database")
        self._opened = True
        return self

    async def __aexit__(self, exc_type, exc_value, traceback) -> None:
        self._opened = False
        await self.engine.dispose()


def get_sessionmaker() -> asql.async_sessionmaker[asql.AsyncSession]:
    """
    Shorthand for getting a sessionmaker from the database manager.
    Issues a warning when getting the sessionmaker from an unopened engine.
    """
    database = AsyncDatabase()
    if not database.is_opened:
        LOGGER.warning("Got sessionmaker of unopened/closed engine!")
    return database.sessionmaker


def get_session() -> asql.AsyncSession:
    """
    Shorthand for getting a new session from the database manager.
    In long form this would be roughly equal to `AsyncDatabase().sessionmaker()`
    Issues a warning when getting the sessionmaker from an unopened engine.
    """
    return get_sessionmaker()()


class may_make_session:
    """
    Context manager that guarantees the returning of a session.
    This allows functions or methods that may accept a session
    to generate one if necessary.
    If a new session was created this helper will close it at exit.
    """
    def __init__(self, session: asql.AsyncSession|None, /):
        self._session = session
        self._creates_session = session is None
    
    async def __aenter__(self) -> asql.AsyncSession:
        if self._creates_session:
            self._session = get_session()
        return self._session  # type: ignore
    
    async def __aexit__(self, exc, exc_type, traceback) -> None:
        if self._creates_session:
            await self._session.close()  # type: ignore


class may_make_session_with_transaction(may_make_session):
    """
    Shorthand with to allow for creation of a transaction with may_make_session.
    Returns both session and transaction.

    `commit_on_close` is a boolean and may be set to True.
        If set, the transaction will always be commited at context exit
        **unlesss** the context exits with an exception.
    """
    def __init__(self, session: asql.AsyncSession|None, commit_on_close: bool=False, /):
        super().__init__(session)
        self._commit_on_close = commit_on_close
    
    async def __aenter__(self) -> tuple[asql.AsyncSession, asql.AsyncSessionTransaction]:
        session = await super().__aenter__()
        self._transaction = await session.begin_nested().__aenter__()
        return session, self._transaction
    
    async def __aexit__(self, exc, exc_type, traceback) -> None:
        if self._commit_on_close and exc is None:
            await self._transaction.commit()
            await self._session.flush()
        await self._transaction.__aexit__(exc, exc_type, traceback)
        return await super().__aexit__(exc, exc_type, traceback)
