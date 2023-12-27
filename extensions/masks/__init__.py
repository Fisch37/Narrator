from logging import getLogger
import discord
from discord.ext import commands
from discord import app_commands
from data.sql.ormclasses import Mask

from extensions.masks.editors import MaskCreatorModal, MaskEditor
from util.coroutine_tools import may_fetch_member

LOGGER = getLogger("extensions.masks")
BOT: commands.Bot


class Masks(commands.Cog):
    mask = app_commands.Group(
        name="mask",
        description="Management command for use of masks.",
        default_permissions=discord.Permissions(),
        guild_only=True
    )
    
    @mask.command(
        name="create",
        description="Create a new mask.",
    )
    async def create_mask(
        self,
        interaction: discord.Interaction
    ):
        creation_modal_prompt = MaskCreatorModal()
        await interaction.response.send_modal(creation_modal_prompt)
        if await creation_modal_prompt.wait():
            # If timed out
            await interaction.followup.send(
                "Woops! It looks like you timed out!",
                ephemeral=True
            )
        # Crash prevention mechanisms
        # (I don't program well, Kaze :c)
        if not isinstance(interaction.user, discord.Member):
            LOGGER.warning("create_mask called with User object in interaction.\
                           This implies a call from DMs which should be impossible.\
                           Trying to salvage...")
            if interaction.guild is None:
                LOGGER.error("Could not salvage create_mask with User. Guild is None!")
                await interaction.followup.send(
                    "Woops! Something went significantly wrong! (Interaction.user is User)",
                    ephemeral=True
                )
                return
            owner = await may_fetch_member(interaction.guild, interaction.user.id)
        else:
            owner = interaction.user
        mask = await Mask.new(
            name=creation_modal_prompt.name.value,
            owner=owner,
            description=creation_modal_prompt.description.value,
            # "" or None == None. This makes some degree of sense, but it's grey magic.
            # TODO: Add some form of URL validation
            avatar_url=creation_modal_prompt.avatar_url.value or None
        )
        embed = discord.Embed(
            title=mask.name,
            description=mask.description
        ).set_image(
            url=mask.avatar_url
        ).set_author(
            name=interaction.user.display_name,
            icon_url=interaction.user.display_avatar.url
        )
        view = MaskEditor(
            None,
            embed,
            owner=owner,
            mask=mask
        )
        message = await interaction.followup.send(
            embed=embed,
            view=view,
            wait=True,
            ephemeral=True
        )
        view.message = message
        await view.update()
        await view.update_message()
    pass


async def setup(bot: commands.Bot):
    global BOT
    BOT = bot
    await bot.add_cog(Masks())
