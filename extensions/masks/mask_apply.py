import asyncio
from logging import getLogger
from typing import NamedTuple
from asyncio import Lock

import discord
from discord.ext.commands import Bot
from data.sql.engine import get_session

from data.sql.ormclasses import AppliedMask, Mask, ensure_id
from util.channel_hierarchy import HierarchySubnode as ChannelOrThread, get_all_parents

User = discord.User|discord.Member|int
Channel = ChannelOrThread|int
LOGGER = getLogger("extensions.masks.mask_apply")


class _AppliedMaskKey(NamedTuple):
    owner_id: int
    channel_id: int


class _SingularMeta(type):
    __object_counts: dict[type, int] = {}
    
    def __call__[Instance](cls: type[Instance], *args, **kwargs) -> Instance:
        _SingularMeta.__object_counts.setdefault(cls, 0)
        _SingularMeta.__object_counts[cls] += 1
        if _SingularMeta.__object_counts[cls] > 1:
            LOGGER.critical(f"Singular class {cls} was initialised more than once!")
        return super().__call__(*args, **kwargs)


class AppliedMaskManager(metaclass=_SingularMeta):
    """
    This is a cache manager for the AppliedMask table.
    It can store information regarding which keys have
    entries in the database as well as the entries themselves.
    
    This Manager can only work so long as it is singular, 
    i. e. there is only one object of this at the same time.
    However, as this object is inherently thread-unsafe, it
    is not a singleton. Trying to create more than one of this 
    object at runtime will be logged for safety purposes.
    """
    def __init__(self):
        self._cache: dict[_AppliedMaskKey, AppliedMask|None] = {}
        """
        Cache for the AppliedMask objects. 
        None signals that there is no database entry for the key.
        """
        self._lock = Lock()
    
    def _store(self, obj: AppliedMask|None, owner_id: int, channel_id: int):
        # Stores an AppliedMask object into the manager. 
        # This operation does not acquire the cache-lock and should never be executed by a user!
        self._cache[_AppliedMaskKey(owner_id, channel_id)] = obj
    
    def _retrieve(self, owner_id: int, channel_id: int) -> "AppliedMask|None":
        # Gets an entry from the cache or raises KeyError if not found.
        # This operation does not acquire the cache-lock and should never be executed by a user!
        return self._cache[_AppliedMaskKey(owner_id, channel_id)]
    
    def _remove(self, owner_id: int, channel_id: int) -> "AppliedMask|None":
        # Marks an entry as non-present in the database and returns the previous entry.
        # Raises KeyError if the entry is not cached.
        # This operation does not acquire the cache-lock and should never be executed by a user!
        key = _AppliedMaskKey(owner_id, channel_id)
        value = self._cache[key]
        self._cache[key] = None
        return value
    
    async def fetch_all(self) -> list[AppliedMask]:
        """
        Fetches all applied mask entries from the database,
        updates the cache, and returns every element.
        """
        applications_list = []
        async with get_session() as session:
            all_applications = await AppliedMask.get_all(session=session)
            async with self._lock:
                self._cache.clear()
                async for app in all_applications:
                    applications_list.append(app)
                    self._store(app, app.owner_id, app.channel_id)
        return applications_list
    
    async def fetch(
        self,
        user: User,
        channel: Channel
    ) -> AppliedMask|None:
        """
        Fetches an applied mask and stores the result in the cache.
        Returns None if no applied mask for this combination exists.
        """
        user = ensure_id(user)
        channel = ensure_id(channel)
        async with self._lock:
            application = await AppliedMask.get(user, channel)
            self._store(application, user, channel)
        return application
    
    async def get(
        self,
        user: User,
        channel: Channel
    ) -> AppliedMask|None:
        """
        Gets an application for the specified combination from the cache or None if no application
        exists for that configuration.
        
        Raises KeyError if the value is not cached.
        """
        user = ensure_id(user)
        channel = ensure_id(channel)
        async with self._lock:
            return self._retrieve(user, channel)
    
    async def may_fetch(self, user: User, channel: Channel) -> AppliedMask|None:
        """
        Guarantees a result for the given combination by accessing the DB only as-needed.
        First tries to retrieve the data from cache and then uses a fetch-operation if the
        data is not in the cache.
        
        Returns the AppliedMask if one exists, or None otherwise.
        """
        try:
            return await self.get(user, channel)
        except KeyError:
            return await self.fetch(user, channel)
    
    async def set(
        self,
        mask: Mask|None,
        user: discord.User|discord.Member,
        channel: ChannelOrThread,
        recursive: bool
    ) -> AppliedMask:
        """
        Sets a new applied mask with the given settings.
        
        This should always be preffered over `AppliedMask.new` 
        as it stores the new entry in the cache and deletes existing ones.
        """
        try:
            await self.remove(user, channel)
        except KeyError:
            pass
        obj = await AppliedMask.new(mask, user, channel, recursive)
        async with self._lock:
            self._store(obj, user.id, channel.id)
        return obj
    
    async def remove(self, user: User, channel: Channel) -> AppliedMask:
        """
        Removes an AppliedMask from the cache and the database.
        
        Raises KeyError if the combination has no AppliedMask entry in the database.
        
        Returns the object that was deleted.
        """
        user = ensure_id(user)
        channel = ensure_id(channel)
        async with self._lock:
            try:
                app = self._remove(user, channel)
            except KeyError:
                # Retaining lock in except-handler to ensure nobody 
                # adds the AppliedMask while I'm deleting it.
                app = await AppliedMask.get(user, channel)
            if app is None:
                raise KeyError(
                    f"Cannot remove non-existent application for ({user},{channel})"
                )
            await app.delete()
            return app
    
    async def hierarchical(self, user: User, channel: ChannelOrThread) -> AppliedMask|None:
        """
        Finds the mask that is relevant for a given channel or thread taking
        hierarchies into consideration. 
        This means a mask applied in a category will be relevant for all channels in it,
        so long as `recursive=True` on the applied mask.
        The lowest point in the hierarchy always takes priority over the others.
        
        Returns the relevant `AppliedMask` object or `None` if no mask is relevant in
        the given context.
        """
        direct = await self.may_fetch(user, channel)
        if direct is not None:
            return direct
        for hierarchy_element in get_all_parents(
            channel,
            include_this=False,
            include_root=False
        ):
            # Once again confusing: the getter part of may_fetch can return None, 
            # which is a valid response. Therefore, so long as the cache is up to date,
            # this will never actually fetch anything.
            app = await self.may_fetch(user, hierarchy_element)
            if app is None or not app.recursive:
                continue
            return app
        # If we never find an applied mask, there isn't one for this combination.
        return None  # This is not required, but I think it's better visually
