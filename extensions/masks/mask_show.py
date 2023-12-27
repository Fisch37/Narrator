"""
This module provides helpers for displaying a mask's information.
"""

from typing import overload
import discord
from discord.ext import commands

from data.sql.ormclasses import Mask


@overload
async def mask_to_embed(
    mask: Mask,
    owner: discord.Member,
    *,
    embed: discord.Embed|None=None
): ...

@overload
async def mask_to_embed(
    mask: Mask,
    *,
    embed: discord.Embed|None=None,
    bot: commands.Bot
): ...

async def mask_to_embed(
    mask: Mask,
    owner: discord.Member|None=None,
    *,
    embed: discord.Embed|None=None,
    bot: commands.Bot|None=None
) -> discord.Embed:
    if embed is None:
        embed = discord.Embed()
    if owner is None:
        owner = await mask.may_fetch_owner(bot)  # type: ignore
    
    embed.title = mask.name
    embed.description = mask.description
    embed.set_image(
        url=mask.avatar_url
    ).set_author(
        name=owner.display_name,
        icon_url=owner.display_avatar.url
    )
    embed.clear_fields()
    for field in mask.fields:
        embed.add_field(
            name=field.name,
            value=field.value,
            inline=field.inline
        )
    return embed
