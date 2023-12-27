from typing import Sequence
from aiocache import cached
import discord
from sqlalchemy import select
from data.sql.engine import get_session

from data.sql.ormclasses import Mask


@cached(30)
async def cached_mask_names_by_member(
    member: discord.Member
) -> Sequence[str]:
    """
    Cached wrapper around `Mask.get_by_owner_and_guild`.
    Does not accept sessions as the cache could otherwise give objects from another session.
    """
    async with get_session() as session:
        result = await session.scalars(
            select(Mask.name)
            .where(Mask.guild_id == member.guild.id)
            .where(Mask.owner_id == member.id)
        )
        return result.all()