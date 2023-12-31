"""
SQL Object Reference Models.
Classes defined herein should **never** be imported outside of database
code! **Outsourcing database interactions is required!**
"""
import asyncio
from typing import overload
from sqlalchemy import ForeignKey, select
from sqlalchemy.orm import mapped_column, Mapped, relationship
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy.ext.orderinglist import OrderingList, ordering_list

from discord.ext.commands import Bot
import discord

from data.sql.engine import Base, Snowflake, may_make_session, may_make_session_with_transaction
from util.coroutine_tools import may_fetch_guild, may_fetch_member, may_fetch_channel_or_thread
from util.channel_hierarchy import HierarchySubnode as ChannelOrThread

def ensure_id(obj: int|discord.abc.Snowflake) -> int:
    if not isinstance(obj, int):
        return obj.id
    else:
        return obj

def _ids_from_member(member: discord.Member|int, guild_id: int|None) -> tuple[int, int]:
    """
    Returns a tuple of member id and guild id extracted from the two parameters.
    `guild_id` may be None if `member` is a `discord.Member` object.
    """
    if isinstance(member, discord.Member):
        member_id = member.id
        guild_id = member.guild.id
    else:
        member_id = member
    return member_id, guild_id  # type: ignore


class Mask(Base):
    """
    SQL Data table for the masks.
    Includes every data content except the fields list, which is stored
    in a seperate table.
    """
    __tablename__ = "masks"

    id: Mapped[int] = mapped_column(
        primary_key=True,
        autoincrement=True,
        init=False
    )
    name: Mapped[str] = mapped_column()
    owner_id: Mapped[Snowflake] = mapped_column()
    guild_id: Mapped[Snowflake] = mapped_column()
    description: Mapped[str] = mapped_column(default="")
    avatar_url: Mapped[str|None] = mapped_column(default=None)
    fields: Mapped[OrderingList["MaskField"]] = relationship(
        order_by="MaskField._index",
        lazy="immediate",
        cascade="all, delete-orphan",
        collection_class=ordering_list("_index"),
        init=False
    )
    
    _billboards: Mapped[list["MaskBillboard"]] = relationship(
        back_populates="mask",
        cascade="delete",  # no delete-orphan because you should never manipulate this thing.
        repr=False,
        init=False
    )
    """KEEP OUT! Only for cascading purposes!"""
    _applications: Mapped[list["AppliedMask"]] = relationship(
        back_populates="mask",
        cascade="delete",  # still don't touch this
        repr=False,
        init=False
    )
    """NO TOUCHY! Only for cascading!"""

    async def may_fetch_owner(self, bot: Bot) -> discord.Member:
        """
        Attempts to get the owner of this mask.
        If the owner is not stored in cache, this will issue an API request.
        If the owner is not found by the API this will raise a discord exception.
        """
        guild = await self.may_fetch_guild(bot)
        return await may_fetch_member(guild, self.owner_id)
    
    async def may_fetch_guild(self, bot: Bot) -> discord.Guild:
        """
        Attempts to get the guild of this mask.
        If the guild is not stored in cache, this will issue an API request.
        If the owner is not found by the API this will raise a discord exception.
        """
        return await may_fetch_guild(bot, self.guild_id)
    
    async def to_embed(self, bot: Bot, embed: discord.Embed|None=None) -> discord.Embed:
        """
        Updates the embed passed in with the mask data.
        If `embed` is None, creates a new embed instead.
        """
        owner = await self.may_fetch_owner(bot)
        if embed is None:
            embed = discord.Embed()
        embed.title = self.name
        embed.timestamp = discord.utils.utcnow()
        embed.description = self.description
        embed.set_author(
            name=owner.display_name,
            icon_url=owner.display_avatar.url
        ).set_thumbnail(
            url=self.avatar_url
        ).clear_fields()
        for field in self.fields:
            embed.add_field(
                name=field.name,
                value=field.value,
                inline=field.inline
            )

        return embed

    async def update(self, *, session: AsyncSession|None=None):
        """
        Updates this object's representation within the database.
        """
        async with may_make_session_with_transaction(session, True) as (session, _):
            session.add(self)

    async def delete(self, *, session: AsyncSession|None=None):
        """
        Deletes this object and its field from the database.
        """
        async with may_make_session_with_transaction(session, True) as (session, _):
            await session.delete(self)
    
    @staticmethod
    async def new(
        *,
        name: str,
        owner: discord.Member,
        session: AsyncSession|None=None,
        **kwargs
    ) -> "Mask":
        """
        Creates a new Mask object with the default attributes and the owner
        given as an argument. The object will immediately be commited
        to the database.
        """
        obj = Mask(
            name=name,
            owner_id=owner.id,
            guild_id=owner.guild.id,
            **kwargs
        )
        async with may_make_session_with_transaction(session, True) as (session, _):
            session.add(obj)
        return obj
    
    @staticmethod
    async def get(id_: int, *, session: AsyncSession|None=None) -> "Mask|None":
        """
        Gets the Mask with the specified id from the database.
        Returns None if not found.
        """
        async with may_make_session(session) as session:
            return await session.get(Mask, id_)
    
    @overload
    @staticmethod
    async def get_by_owner_and_guild(
        owner: discord.Member,
        *,
        session: AsyncSession|None=None
    ) -> list["Mask"]:
        ...

    @overload
    @staticmethod
    async def get_by_owner_and_guild(
        owner: int,
        guild_id: int,
        *,
        session: AsyncSession|None=None
    ) -> list["Mask"]:
        ...

    @staticmethod
    async def get_by_owner_and_guild(
        owner: int|discord.Member,
        guild_id: int|None=None,
        *,
        session: AsyncSession|None=None
    ) -> list["Mask"]:
        """
        Gets all masks owned by the `owner` within the specified guild.
        Accepts a `discord.Member` argument in replacement of `guild_id`.
        """
        owner_id, guild_id = _ids_from_member(owner, guild_id)
        async with may_make_session(session) as session:
            result = await session.scalars(
                select(Mask)
                .where(Mask.owner_id == owner_id and Mask.guild_id == guild_id)  # type: ignore
            )
            return list(result.all())
    
    @staticmethod
    @overload
    async def get_by_name_and_owner_and_guild(
        name: str,
        owner: int,
        guild_id: int,
        *,
        session: AsyncSession|None=None
    ) -> "Mask|None": 
        ...
    
    @staticmethod
    @overload
    async def get_by_name_and_owner_and_guild(
        name: str,
        owner: discord.Member,
        *,
        session: AsyncSession|None=None
    ) -> "Mask|None":
        ...
    
    @staticmethod
    async def get_by_name_and_owner_and_guild(
        name: str,
        owner: discord.Member|int,
        guild_id: int|None=None,
        *,
        session: AsyncSession|None=None
    ) -> "Mask|None":
        owner_id, guild_id = _ids_from_member(owner, guild_id)
        async with may_make_session(session) as session:
            return await session.scalar(
                select(Mask)
                .where(Mask.owner_id == owner_id)
                .where(Mask.guild_id == guild_id)
                .where(Mask.name == name)
            )


class MaskField(Base):
    """
    Table storing all fields. Each stored field has an id added to it
    to allow the ORM to read it. Otherwise, fields are tagged with their
    index and mask id
    """
    __tablename__ = "mask_fields"

    mask_id: Mapped[int] = mapped_column(
        ForeignKey("masks.id"),
        init=False,
        primary_key=True
    )
    # NOTE: This may cause issues with OrderingList (see the docs)
    _index: Mapped[int] = mapped_column(init=False, primary_key=True)
    name: Mapped[str]
    value: Mapped[str]
    inline: Mapped[bool]
    
    def __repr__(self) -> str:
        return f'<{type(self).__name__} {self.mask_id}:{self._index} inline={self.inline} name={self.name!r}>'


class MaskBillboard(Base):
    """
    Stores data about published masks.
    """
    __tablename__ = "billboards"
    
    mask_id: Mapped[int] = mapped_column(
        ForeignKey(Mask.id),
        primary_key=True,
        init=False
    )
    mask: Mapped[Mask] = relationship(
        # cascade=""
    )
    refresh_id: Mapped[str]
    channel_id: Mapped[Snowflake]
    guild_id: Mapped[Snowflake]
    message_id: Mapped[Snowflake] = mapped_column(primary_key=True)
    
    @staticmethod
    async def new(
        mask: Mask,
        refresh_id: str,
        message: discord.Message,
        guild: discord.Guild,
        *,
        session: AsyncSession|None=None
    ) -> "MaskBillboard":
        obj = MaskBillboard(
            mask=mask,
            refresh_id=refresh_id,
            channel_id=message.channel.id,
            guild_id=guild.id,
            message_id=message.id
        )
        async with may_make_session_with_transaction(session, True) as (session, _):
            session.add(obj)
            await session.flush()
        return obj
    
    @staticmethod
    async def get_all(
        *,
        session: AsyncSession|None=None
    ):
        async with may_make_session(session) as session:
            return await session.stream_scalars(
                select(MaskBillboard)
                .execution_options(yield_per=10)
            )
    
    async def delete(
        self,
        *,
        session: AsyncSession|None=None
    ):
        async with may_make_session_with_transaction(session, True) as (session, _):
            await session.delete(self)
    
    async def fetch_message(self, bot: Bot) -> discord.Message:
        guild = await may_fetch_guild(bot, self.guild_id)
        channel = await may_fetch_channel_or_thread(guild, self.channel_id)
        if not hasattr(channel, "fetch_message"):
            raise TypeError(
                "Attempted to call fetch_message on Billboard in CategoryChannel!"
                + "What? How? Why? You goofed! You seriously goofed! This should never happen!"
            )
        # Apparently type checkers don't have hasattr as a TypeGuard-ish thing?
        return await channel.fetch_message(self.message_id)  # type: ignore


class AppliedMask(Base):
    """Holds information about how a mask is applied in a given channel"""
    
    __tablename__ = "applied_masks"
    
    mask_id: Mapped[int] = mapped_column(ForeignKey(Mask.id), init=False)
    mask: Mapped[Mask] = relationship(cascade="", lazy="immediate")
    channel_id: Mapped[Snowflake] = mapped_column(primary_key=True)
    guild_id: Mapped[Snowflake]
    owner_id: Mapped[Snowflake] = mapped_column(primary_key=True)
    recursive: Mapped[bool]
    
    @staticmethod
    async def new(
        mask: Mask,
        owner: discord.Member|discord.User,
        channel: ChannelOrThread,
        recursive: bool,
        *,
        session: AsyncSession|None=None
    ) -> "AppliedMask":
        obj = AppliedMask(
            mask,
            channel.id,
            channel.guild.id,
            owner.id,
            recursive
        )
        async with may_make_session_with_transaction(session, True) as (session, _):
            session.add_all((obj, mask))
            await session.flush()
        return obj
    
    @staticmethod
    async def get(
        owner: int|discord.User|discord.Member,
        channel: int|ChannelOrThread,
        *,
        session: AsyncSession|None=None
    ) -> "AppliedMask|None":
        owner = ensure_id(owner)
        channel = ensure_id(channel)
        async with may_make_session(session) as session:
            return await session.get(AppliedMask, (owner, channel))
    
    @staticmethod
    async def get_all(*, session: AsyncSession):
        async with may_make_session(session) as session:
            return await session.stream_scalars(
                select(AppliedMask)
                .execution_options(yield_per=10)
            )
    
    async def update(self, *, session: AsyncSession|None=None):
        async with may_make_session_with_transaction(session, True) as (session, _):
            session.add(self)
    
    async def delete(self, *, session: AsyncSession|None=None):
        async with may_make_session_with_transaction(session, True) as (session, _):
            await session.delete(self)
    
    async def may_fetch_channel(self, bot: Bot):
        guild = await may_fetch_guild(bot, self.guild_id)
        return await may_fetch_channel_or_thread(guild, self.channel_id)
    
    async def get_mask(self, *, session: AsyncSession|None=None) -> Mask:
        """
        Returns the mask associated with this application.
        In contrast to awaitable_attrs this does not require
        this object to be part of a session.
        """
        async with may_make_session(session) as session:
            needs_adding = self not in session
            if needs_adding:
                session.add(self)
            try:
                return await self.awaitable_attrs.mask
            finally:
                # This may be an uncommon way to do it, but it feels better
                if needs_adding:
                    session.expunge(self)
    
    async def to_embed(
        self,
        bot: Bot,
        embed: discord.Embed|None=None
    ) -> discord.Embed:
        """Generates or overrides a passed embed to represent this object."""
        if embed is None:
            embed = discord.Embed()
        
        channel_task = asyncio.create_task(self.may_fetch_channel(bot))
        owner_task = asyncio.create_task(self.mask.may_fetch_owner(bot))
        channel = await channel_task
        owner = await owner_task
        
        embed.title = self.mask.name
        embed.colour = discord.Colour.blue()
        embed.set_author(name=owner.display_name, icon_url=owner.display_avatar.url)
        embed.set_image(url=self.mask.avatar_url)
        
        embed.clear_fields()
        embed.add_field(name="Channel", value=channel.mention)
        embed.add_field(
            name="Includes Subchannels",
            value=":white_check_mark:" if self.recursive else ":x:"
        )
        
        return embed
