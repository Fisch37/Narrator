"""
High-Level API for masks.
This should always be used in bot code as an abstraction to avoid
direct calls to SQL.
"""
from dataclasses import dataclass
import discord
from util import LimitedList

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
