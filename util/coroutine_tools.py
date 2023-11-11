"""
Provides helpers for coroutine functions.
Provides may-fetch functions that switch from cache to API when necessary.
Also includes the may_fetch_generator function, 
that allows dynamic generation of may-fetch-functions.
"""
from typing import Callable, TypeVar, Any, TypeVarTuple
from collections.abc import Coroutine
from discord import Guild
from discord.ext.commands import Bot

T = TypeVar('T')
Ts = TypeVarTuple('Ts')

def may_fetch_generator(
        getter: Callable[[*Ts],T|None],
        fetcher: Callable[[*Ts],Coroutine[Any,Any,T]],
) -> Callable[[*Ts],Coroutine[Any,Any,T]]:
    """
    Returns a may-fetch function that switches between caching function and API call when necessary.
    may-fetch functions work by first calling the cache-function (which is called the "getter")
    and, if the getter returns None, calling and awaiting the API function ("fetcher").
    
    The getter and fetcher are expected to have the same argument structure and should return the
    same object type. 

    The may-fetch function is always a coroutine function though it does not necessarily await
    anything when called.
    """
    async def may_fetch(*args: *Ts) -> T:
        result = getter(*args)
        if result is None:
            result = await fetcher(*args)
        return result
    return may_fetch

may_fetch_guild = may_fetch_generator(Bot.get_guild,Bot.fetch_guild)
may_fetch_user = may_fetch_generator(Bot.get_user,Bot.fetch_user)
may_fetch_member = may_fetch_generator(Guild.get_member,Guild.fetch_member)
