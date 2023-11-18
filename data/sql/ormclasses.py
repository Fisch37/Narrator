"""
SQL Object Reference Models.
Classes defined herein should **never** be imported outside of database
code! **Outsourcing database interactions is required!**
"""
from sqlalchemy import ForeignKey, UniqueConstraint
from sqlalchemy.orm import DeclarativeBase, mapped_column, Mapped, relationship
from typing_extensions import Annotated

from discord.ext.commands import Bot
import discord

from data.sql.type_decorators import HugeInt
from util.limited_list import FieldsList
from util.coroutine_tools import may_fetch_guild, may_fetch_member

Snowflake = Annotated[int, "Snowflake"]


class Base(DeclarativeBase):
    """Base class for declarative SQL classes found below."""
    type_annotation_map = {
        Snowflake: HugeInt
    }


class Mask(Base):
    """
    SQL Data table for the masks.
    Includes every data content except the fields list, which is stored
    in a seperate table.
    """
    __tablename__ = "masks"

    id: Mapped[int] = mapped_column(
        primary_key=True,
        autoincrement=True
    )
    name: Mapped[str] = mapped_column()
    description: Mapped[str] = mapped_column()
    avatar_url: Mapped[str|None] = mapped_column()
    owner_id: Mapped[Snowflake] = mapped_column()
    guild_id: Mapped[Snowflake] = mapped_column()
    fields: Mapped[FieldsList["MaskField"]] = relationship(  # type: ignore
        order_by="MaskField.index",
        lazy="joined",
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


class MaskField(Base):
    """
    Table storing all fields. Each stored field has an id added to it
    to allow the ORM to read it. Otherwise, fields are tagged with their
    index and mask id
    """
    __tablename__ = "mask_fields"

    id: Mapped[int] = mapped_column(primary_key=True)
    mask_id: Mapped[int] = mapped_column(ForeignKey("masks.id"))
    index: Mapped[int] = mapped_column()
    name: Mapped[str] = mapped_column()
    value: Mapped[str] = mapped_column()
    inline: Mapped[bool] = mapped_column()

    __table_args__ = (
        UniqueConstraint(
            "mask_id",
            "index",
            name="list_position_uniqueness"
        ),
    )
