from itertools import islice
from logging import getLogger
from aiocache import cached
import discord
from discord.ext import commands
from discord import app_commands
from data.sql.ormclasses import Mask

from extensions.masks.mask_editor import MaskCreatorModal, MaskEditor
from extensions.masks.mask_show import mask_to_embed
from util.confirmation_view import ConfirmationView
from util.coroutine_tools import may_fetch_member

LOGGER = getLogger("extensions.masks")
BOT: commands.Bot

@cached(30)
async def cached_masks_by_member(
    member: discord.Member
) -> list[Mask]:
    """
    Cached wrapper around `Mask.get_by_owner_and_guild`.
    Does not accept sessions as the cache could otherwise give objects from another session.
    """
    return await Mask.get_by_owner_and_guild(member)

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
        embed = await mask_to_embed(mask, interaction.user)
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
    
    @mask.command(
        name="edit",
        description="Edit an existing mask"
    )
    @app_commands.rename(mask_name="mask")
    @app_commands.describe(
        mask_name="The name of the mask you seek to edit."
    )
    async def edit_mask(
        self,
        interaction: discord.Interaction,
        mask_name: str
    ):
        mask = await Mask.get_by_name_and_owner_and_guild(mask_name, interaction.user)
        if mask is None:
            await interaction.response.send_message(
                ":x: That mask doesn't seem to exist!",
                ephemeral=True
            )
            return
        await interaction.response.defer(ephemeral=True)
        embed = await mask_to_embed(mask, interaction.user)
        view = MaskEditor(
            None,
            embed,
            owner=interaction.user,
            mask=mask
        )
        message = await interaction.followup.send(view=view, embed=embed)
        view.message = message
        await view.update()
        await view.update_message()
    
    @mask.command(
        name="remove",
        description="Delete an existing mask. This operation cannot be undone!"
    )
    @app_commands.rename(mask_name="mask")
    @app_commands.describe(
        mask_name="The name of the mask you want to remove."
    )
    async def mask_remove(
        self,
        interaction: discord.Interaction,
        mask_name: str
    ):
        mask = await Mask.get_by_name_and_owner_and_guild(mask_name, interaction.user)
        if mask is None:
            await interaction.response.send_message(
                ":x: That mask doesn't seem to exist!",
                ephemeral=True
            )
            return
        
        embed = await mask_to_embed(mask, interaction.user)
        view = ConfirmationView(
            confirm_style=discord.ButtonStyle.danger,
            cancel_style=discord.ButtonStyle.success
        )
        await interaction.response.send_message(
            "Are you sure you want to remove this mask? This cannot be undone.",
            embed=embed,
            view=view,
            ephemeral=True
        )
        try:
            should_delete = await view
        except TimeoutError:
            return
        if should_delete:
            await mask.delete()
            await interaction.followup.send(
                ":wastebasket: Mask deleted!",
                ephemeral=True
            )
        else:
            await interaction.followup.send(
                ":white_check_mark: Mask deletion cancelled!",
                ephemeral=True
            )
    
    @edit_mask.autocomplete("mask_name")
    @mask_remove.autocomplete("mask_name")
    async def _mask_name_autocomplete(
        self,
        interaction: discord.Interaction,
        mask_name: str
    ) -> list[app_commands.Choice]:
        if interaction.guild is None:
            return []
        masks = await cached_masks_by_member(interaction.user)
        filtered_masks = filter(lambda m: m.name.startswith(mask_name), masks)
        return [
            app_commands.Choice(
                name=m.name,
                value=m.name
            )
            for m in islice(filtered_masks, 25)
        ]
    pass


async def setup(bot: commands.Bot):
    global BOT
    BOT = bot
    await bot.add_cog(Masks())
