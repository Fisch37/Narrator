"""
High-Level API for masks.
This should always be used in bot code as an abstraction to avoid
direct calls to SQL.
"""
from logging import getLogger
from typing import Iterable, Self, overload
import asyncio
import discord
from discord.ext.commands import Bot
from sqlalchemy import select, update
from pydantic import BaseModel, ConfigDict
from data.sql.ormclasses import Mask as SQLMask, MaskField as SQLMaskField
from data.sql.engine import get_session
from util import LimitedList
from util.coroutine_tools import may_fetch_guild, may_fetch_member

EMBED_MAX_FIELDS = 25
LOGGER = getLogger("data.masks")


class Field(BaseModel):
    """
    Abstraction of Embed fields.
    Includes an id for database connection.
    """
    id: int|None
    name: str
    value: str
    inline: bool = True

    async def update(self) -> Self:
        """
        Updates the database with the current data of this field instance.
        """
        async with get_session() as session:
            await session.execute(
                update(SQLMaskField),
                self.model_dump(mode="json")
            )
            await session.commit()
        return self

    @staticmethod
    async def update_bulk(fields: Iterable["Field"]) -> None:
        """
        Bulk-updates all the passed instances in one sql statement.
        This should be the preferred option for any updating of more than one field.
        """
        async with get_session() as session:
            await session.execute(
                update(SQLMaskField),
                [f.model_dump(mode="json") for f in fields]
            )
            await session.commit()

    @staticmethod
    def from_sql(sqlfield: SQLMaskField) -> "Field":
        """
        Converts an SQLSQLMaskFields object into a Field object.
        """
        return Field(
            id=sqlfield.id,
            name=sqlfield.name,
            value=sqlfield.value,
            inline=sqlfield.inline
        )

    @staticmethod
    async def get_by_mask_id(mask_id: int):
        """
        Get all fields that correspond to a mask, specified by its id.
        Fields are ordered by their index.
        """
        async with get_session() as session:
            sqlfields_iterator = await session.scalars(
                select(SQLMaskField)
                .where(SQLMaskField.mask_id == mask_id)
                .order_by(SQLMaskField.index)
            )
            return (
                Field.from_sql(sqlfield)
                for sqlfield in sqlfields_iterator
            )


class Mask(BaseModel):
    """
    High-level class for a single mask. (Webhook-Alias)
    Should store all information on a singular mask, when expanded.
    """
    model_config = ConfigDict(arbitrary_types_allowed=True)

    id: int
    name: str
    description: str
    avatar_url: str|None
    fields: LimitedList[Field]
    owner: discord.Member

    async def update(self) -> Self:
        """
        Updates the database entries associated with this mask.
        This method also updates the fields in parallel.
        """
        field_update = asyncio.create_task(
            Field.update_bulk(self.fields)
        )
        async with get_session() as session:
            sqlvalues = self.model_dump(
                mode="json",
                exclude={"_fields", "owner", "guild"}
            )
            sqlvalues["owner"] = str(self.owner.id)
            sqlvalues["guild"] = str(self.owner.guild.id)
            await session.execute(
                update(SQLMask),
                sqlvalues
            )
            await session.commit()
        await field_update
        return self

    def to_embed(self, embed: discord.Embed|None=None) -> discord.Embed:
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

    @staticmethod
    async def _from_sql(
        sqlmask: SQLMask,
        fields: LimitedList[Field],
        /,
        owner: discord.Member,
    ) -> "Mask":
        return Mask(
            id=sqlmask.id,
            name=sqlmask.name,
            description=sqlmask.description,
            avatar_url=sqlmask.avatar_url,
            fields=fields,
            owner=owner
        )

    @staticmethod
    async def _from_sql_no_fields(
        sqlmask: SQLMask,
        owner: discord.Member,
    ) -> "Mask":
        fields = LimitedList(
            await Field.get_by_mask_id(mask_id=sqlmask.id),
            size=EMBED_MAX_FIELDS
        )
        return await Mask._from_sql(
            sqlmask,
            fields,
            owner
        )

    @staticmethod
    async def _from_sql_no_fields_or_discord_data(
        sqlmask: SQLMask,
        bot: Bot
    ) -> "Mask":
        guild = await may_fetch_guild(bot, int(sqlmask.guild_id))
        owner = await may_fetch_member(guild, int(sqlmask.owner_id))
        return await Mask._from_sql_no_fields(
            sqlmask,
            owner
        )

    @staticmethod
    async def get_from_id(id_: int, bot: Bot) -> "Mask|None":
        """
        Gets a high-level Mask object with the id id_.
        Returns the newly created Mask object or None if not found.
        """
        async with get_session() as session:
            sqlmask = await session.get(SQLMask, id_)
            if sqlmask is None:
                return None

            return await Mask._from_sql_no_fields_or_discord_data(
                sqlmask,
                bot
            )

    @overload
    @staticmethod
    async def get_by_owner(owner: discord.Member) -> list["Mask"]:
        ...

    @overload
    @staticmethod
    async def get_by_owner(owner: int, bot: Bot) -> list["Mask"]:
        ...

    @staticmethod
    async def get_by_owner(owner: discord.Member|int, bot: Bot|None=None) -> list["Mask"]:
        """
        Gets all masks associated with a specific user.
        The owner argument may be either a discord.User object or an int being the user id.
        """
        if isinstance(owner, discord.Member):
            owner_id = owner.id
        else:
            if bot is None:
                raise ValueError("Argument bot is required when owner is an integer.")
            owner_id = owner
        async with get_session() as session:
            sqlmasks_iterator = await session.scalars(
                select(SQLMask)
                .where(SQLMask.owner_id == str(owner_id))
            )
            return await asyncio.gather(*(
                (
                    Mask._from_sql_no_fields(
                        sqlmask,
                        owner
                    ) if isinstance(owner, discord.Member)
                    else Mask._from_sql_no_fields_or_discord_data(
                        sqlmask,
                        bot  # type: ignore
                    )
                )
                for sqlmask in sqlmasks_iterator
            ))

    @staticmethod
    async def new(owner: discord.Member) -> "Mask":
        """
        Creates a new, empty Mask and stores it in the database.
        """
        async with get_session() as session:
            sqlmask = SQLMask(
                name="",
                description="",
                avatar_url=None,
                owner=str(owner.id),
                guild=str(owner.guild.id)
            )
            session.add(sqlmask)
            await session.commit()
        return await Mask._from_sql(sqlmask, LimitedList(), owner)
