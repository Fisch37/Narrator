"""
This module provides helpers for displaying a mask's information.
"""

import asyncio
from logging import getLogger
from typing import overload

import discord
from discord import ui
from discord.ext import commands
from data.sql.engine import get_session

from data.sql.ormclasses import Mask, MaskBillboard
from util.editor.owned import OwnedEditor
from util.snowflakes import generate_snowflake

LOGGER = getLogger("extensions.masks.mask_show")


@overload
async def mask_to_embed(
    mask: Mask,
    owner: discord.Member,
    *,
    embed: discord.Embed|None=None
) -> discord.Embed: ...

@overload
async def mask_to_embed(
    mask: Mask,
    *,
    embed: discord.Embed|None=None,
    bot: commands.Bot
) -> discord.Embed: ...

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


class PrivateShowView(ui.View):
    """
    Has a single button labelled publish to publish the targetted mask.
    """
    def __init__(self, mask: Mask, *, timeout: float=180):
        self.mask = mask
        super().__init__(timeout=timeout)
    
    @ui.button(label="Publish", emoji="\u2709", style=discord.ButtonStyle.primary)
    async def publish(self, interaction: discord.Interaction, _):
        await interaction.response.defer()
        embed = await mask_to_embed(self.mask, interaction.user)
        message = await interaction.followup.send(
            embed=embed,
            wait=True
        )
        if not isinstance(interaction.user, discord.Member):
            LOGGER.warning(
                f"PrivateShowView.publish: interaction.user is type {type(interaction.user)}\
                , not discord.Member"
            )
        await PublicShowView.new(
            message,
            embed,
            interaction.user,
            self.mask
        )
        self.stop()


class PublicShowView(OwnedEditor, timeout=None):
    """
    Allows for refreshing of published masks by their publisher.
    This view is persistent, meaning it should be stored in the database after it was created.
    Classmethods allow for this to happen automatically without further user interaction.
    
    Publishing means posting the embed information about the mask in a non-ephemeral way.
    """
    REFRESH_COOLDOWN = 60
    
    def __init__(
        self,
        message: discord.Message|None=None,
        embed: discord.Embed|None=None,
        *,
        owner: discord.Member,
        mask: Mask,
        refresh_id: str|None
    ):
        self.mask = mask
        super().__init__(message, embed, owner=owner)
        if refresh_id is not None:
            self.refresh.custom_id = refresh_id
        pass
    
    async def update(self):
        async with get_session() as session:
            session.add(self.mask)
            # Doing refresh and field refreshes in sequence because I'm afraid of orphans
            await session.refresh(self.mask)
            async with asyncio.TaskGroup() as tg:
                for field in self.mask.fields:
                    tg.create_task(session.refresh(field))
        self.embed = await mask_to_embed(self.mask, self.owner, embed=self.embed)
    
    async def _enable_later(self):
        await asyncio.sleep(type(self).REFRESH_COOLDOWN)
        self.refresh.disabled = False
        await self.update_message()
    
    @ui.button(label="Refresh", style=discord.ButtonStyle.green, emoji="\U0001F501")
    async def refresh(self, interaction: discord.Interaction, _):
        if interaction.user != self.owner:
            await interaction.response.send_message(
                ":x: Only the owner of this mask can refresh it!",
                ephemeral=True
            )
            return
        self.refresh.disabled = True
        asyncio.create_task(self._enable_later())
        await interaction.response.defer()
    
    
    @classmethod
    async def new[T: "PublicShowView"](
        cls: type[T],
        message: discord.Message,
        embed: discord.Embed,
        owner: discord.Member,
        mask: Mask
    ) -> T:
        """
        Generates a new view from passed arguments and sets it on the message.
        
        This is preferable to a normal __init__ call because it also creates a DB entry.
        """
        obj = cls(
            message=message,
            embed=embed,
            owner=owner,
            mask=mask,
            refresh_id=hex(generate_snowflake())[2:]
        )
        async with asyncio.TaskGroup() as tg:
            tg.create_task(MaskBillboard.new(
                mask,
                obj.refresh.custom_id,  # type: ignore
                message,
                owner.guild
            ))
            tg.create_task(message.edit(view=obj))
        
        return obj
    
    @classmethod
    async def from_billboard[T: "PublicShowView"](
        cls: type[T],
        billboard: MaskBillboard,
        bot: commands.Bot
    ) -> T:
        """
        Generates a view from an existing sql entry.
        Requires the billboard instance to be attached to a session.
        """
        async def fetch_mask_and_owner():
            mask: Mask = await billboard.awaitable_attrs.mask
            return mask, await mask.may_fetch_owner(bot)
        
        async with asyncio.TaskGroup() as tg:
            message_task = tg.create_task(billboard.fetch_message(bot))
            mask_task = tg.create_task(fetch_mask_and_owner())
        
        message = message_task.result()
        mask, owner = mask_task.result()
        return cls(
            message=message,
            embed=message.embeds[0],
            owner=owner,
            mask=mask,
            refresh_id=billboard.refresh_id
        )

async def summon_all_public_show_views(bot: commands.Bot, /) -> list[PublicShowView]:
    
    tasks = []
    async with get_session() as session, asyncio.TaskGroup() as tg:
        async for billboard in await MaskBillboard.get_all(session=session):
            tasks.append(
                tg.create_task(PublicShowView.from_billboard(billboard, bot))
            )
    return [t.result() for t in tasks]
