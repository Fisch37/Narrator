"""
SQL Object Reference Models.
Classes defined herein should **never** be imported outside of database
code! **Outsourcing database interactions is required!**
"""
from typing import overload
from sqlalchemy import ForeignKey, UniqueConstraint, select
from sqlalchemy.orm import mapped_column, Mapped, relationship
from sqlalchemy.ext.asyncio import AsyncSession

from discord.ext.commands import Bot
import discord
from data.sql.engine import Base, Snowflake, may_make_session, may_make_session_with_transaction
from data.sql.special_types import FieldsList

from util.coroutine_tools import may_fetch_guild, may_fetch_member


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
    fields: Mapped[FieldsList["MaskField"]] = relationship(  # type: ignore
        order_by="MaskField._index",
        lazy="immediate",
        default_factory=FieldsList,
        cascade="all, delete-orphan"
    )

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
        for i, field in enumerate(self.fields):
            field.mask_id = self.id
            field.set_field_index(i)
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
        if isinstance(owner, discord.Member):
            owner_id = owner.id
            guild_id = owner.guild.id
        else:
            owner_id = owner
        async with may_make_session(session) as session:
            result = await session.scalars(
                select(Mask)
                .where(Mask.owner_id == owner_id and Mask.guild_id == guild_id)  # type: ignore
            )
            return list(result.all())


class MaskField(Base):
    """
    Table storing all fields. Each stored field has an id added to it
    to allow the ORM to read it. Otherwise, fields are tagged with their
    index and mask id
    """
    __tablename__ = "mask_fields"

    id: Mapped[int] = mapped_column(
        primary_key=True,
        init=False
    )
    mask_id: Mapped[int] = mapped_column(
        ForeignKey("masks.id"),
        init=False
    )
    _index: Mapped[int] = mapped_column(init=False)
    name: Mapped[str] = mapped_column()
    value: Mapped[str] = mapped_column()
    inline: Mapped[bool] = mapped_column()

    __table_args__ = (
        UniqueConstraint(
            "mask_id",
            "_index",
            name="list_position_uniqueness"
        ),
    )

    def set_field_index(self, index: int) -> None:
        """
        Updates the _index value of this object.
        This should not be used outside of database operations.
        """
        self._index = index
