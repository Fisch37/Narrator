"""
High-Level API for masks.
This should always be used in bot code as an abstraction to avoid
direct calls to SQL.
"""
from dataclasses import dataclass
import asyncio
import discord
from discord.ext.commands import Bot
from sqlalchemy import select
from data.sql.ormclasses import SQLMasks, SQLMaskFields
from data.sql.engine import get_session
from util import LimitedList

EMBED_MAX_FIELDS = 25

@dataclass
class Field:
    """
    Abstraction of Embed fields.
    Includes an id for database connection.
    """
    id: int|None
    name: str
    value: str
    inline: bool = True

    @staticmethod
    def from_sql(sqlfield: SQLMaskFields) -> "Field":
        """
        Converts an SQLMaskFields object into a Field object.
        """
        return Field(
            sqlfield.id,
            sqlfield.name,
            sqlfield.value,
            sqlfield.inline
        )

    @staticmethod
    async def get_by_mask_id(mask_id: int):
        async with get_session() as session:
            sqlfields_iterator = await session.scalars(
                select(SQLMaskFields)
                .where(SQLMaskFields.mask_id == mask_id)
                .order_by(SQLMaskFields.index)
            )
            return (
                Field.from_sql(sqlfield)
                for sqlfield in sqlfields_iterator
            )


@dataclass
class Mask:
    """
    High-level class for a single mask. (Webhook-Alias)
    Should store all information on a singular mask, when expanded.
    """
    id: int
    name: str
    description: str
    avatar_url: str
    _fields: LimitedList[Field]
    owner: discord.User

    def to_embed(self, embed: discord.Embed=None) -> discord.Embed:
        """
        Generate or update an Embed with the information of this mask.
        """
        if embed is None:
            embed = discord.Embed()
        embed.title = self.name
        embed.timestamp = discord.utils.utcnow()
        embed.description = self.description
        embed.set_author(
            name=self.owner.display_name,
            icon_url=self.owner.display_avatar.url
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

    @property
    def fields(self) -> LimitedList[Field]:
        """
        The fields of the 
        """
        return self._fields


    @staticmethod
    async def _from_sql(
        sqlmask: SQLMasks,
        fields: LimitedList[Field],
        /,
        bot: Bot,
        owner: discord.User|None=None
    ) -> "Mask":
        if owner is None:
            # This is a slow-down when executed from _make_without_fields.
            # However: Fixing this would obfuscate code and could introduce bugs.
            owner = bot.get_user() or await bot.fetch_user(int(sqlmask.owner))
        return Mask(
            sqlmask.id,
            sqlmask.name,
            sqlmask.description,
            sqlmask.avatar_url,
            fields,
            owner
        )

    @staticmethod
    async def _make_without_fields(
        sqlmask: SQLMasks,
        bot: Bot
    ) -> "Mask":
        fields = LimitedList(
            await Field.get_by_mask_id(mask_id=sqlmask.id),
            size=EMBED_MAX_FIELDS
        )
        return await Mask._from_sql(sqlmask,fields,bot)

    @staticmethod
    async def get_from_id(id_: int, bot: Bot) -> "Mask|None":
        """
        Gets a high-level Mask object with the id id_.
        Returns the newly created Mask object or None if not found.
        """
        async with get_session() as session:
            sqlmask = await session.get(SQLMasks,id_)
            if sqlmask is None:
                return None

            return await Mask._make_without_fields(sqlmask,bot)

    @staticmethod
    async def get_by_owner(owner: discord.User|int, bot: Bot) -> list["Mask"]:
        if isinstance(owner,discord.User):
            owner_id = owner.id
        else:
            owner_id = owner
        async with get_session() as session:
            sqlmasks_iterator = await session.scalars(
                select(SQLMasks)
                .where(SQLMasks.owner == str(owner_id))
            )
            return await asyncio.gather(*(
                Mask._make_without_fields(sqlmask, bot)
                for sqlmask in sqlmasks_iterator
            ))
