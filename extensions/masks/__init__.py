import asyncio
from logging import getLogger
import discord
from discord.ext import commands
from discord import app_commands
from data.sql.ormclasses import Mask

from extensions.masks.mask_editor import EditCollisionError, MaskCreatorModal, MaskEditor
from extensions.masks.mask_show import PrivateShowView, mask_to_embed, summon_all_public_show_views
from extensions.masks.mask_transformer import MaskParameter, MaskTransformer
from util.confirmation_view import ConfirmationView
from util.coroutine_tools import may_fetch_member

LOGGER = getLogger("extensions.masks")
BOT: commands.Bot


class Masks(commands.Cog):
    async def _summon_public_views_stored(self):
        # FIXME: Persistent views created here don't respond to interactions
        self._public_show_views = await summon_all_public_show_views(BOT)
        for view in self._public_show_views:
            BOT.add_view(view)
        pass
    
    async def cog_load(self) -> None:
        asyncio.create_task(self._summon_public_views_stored())
        return await super().cog_load()
    
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
    @app_commands.describe(
        mask="The name of the mask you seek to edit."
    )
    async def edit_mask(
        self,
        interaction: discord.Interaction,
        mask: MaskParameter
    ):
        await interaction.response.defer(ephemeral=True)
        embed = await mask_to_embed(mask, interaction.user)
        while True:
            try:
                view = MaskEditor(
                    None,
                    embed,
                    owner=interaction.user,
                    mask=mask
                )
            except EditCollisionError as e:
                has_closed_collision = await self._close_colliding_editor_if_requested(
                    interaction,
                    e.editor
                )
                if not has_closed_collision:
                    await interaction.followup.send(
                        "Alright! Bye bye!",
                        ephemeral=True
                    )
                    return
            else:
                break
        message = await interaction.followup.send(view=view, embed=embed, ephemeral=True)
        view.message = message
        await view.update()
        await view.update_message()
    
    @mask.command(
        name="remove",
        description="Delete an existing mask. This operation cannot be undone!"
    )
    @app_commands.describe(
        mask="The name of the mask you want to remove."
    )
    async def mask_remove(
        self,
        interaction: discord.Interaction,
        mask: MaskParameter
    ):
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
    
    @mask.command(
        name="show",
        description="Show or publish a mask."
    )
    @app_commands.describe(
        mask="The mask to show the information of."
    )
    async def mask_show(
        self,
        interaction: discord.Interaction,
        mask: MaskParameter
    ):
        embed = await mask_to_embed(mask, interaction.user)
        view = PrivateShowView(mask)
        await interaction.response.send_message(
            embed=embed,
            view=view,
            ephemeral=True
        )
    
    @edit_mask.error
    @mask_remove.error
    @mask_show.error
    async def _mask_transform_error_handler(
        self,
        interaction: discord.Interaction,
        error: app_commands.AppCommandError
    ) -> None:
        if (
            isinstance(error, app_commands.TransformerError) 
            and isinstance(error.transformer, MaskTransformer)
        ):
            await interaction.response.send_message(
                ":x: That mask doesn't seem to exist!",
                ephemeral=True
            )
            return
    
    async def _close_colliding_editor_if_requested(
        self,
        interaction: discord.Interaction,
        /,
        collision: MaskEditor
    ) -> bool:
        """
        Asks the user if they want to close the editor that is colliding and does so if requested.
        
        Returns a boolean whether the editor was closed.
        """
        confirm_view = ConfirmationView(
            confirm_style=discord.ButtonStyle.danger,
            cancel_style=discord.ButtonStyle.success
        )
        await interaction.followup.send(
            ":warning: This mask already has an open editor! Would you like to close it?",
            ephemeral=True,
            view=confirm_view
        )
        should_close = await confirm_view
        if should_close:
            collision.stop()
            await collision # Wait for on_end to finish. 
            # Avoids race condition with the loop in edit_mask
        return should_close
    pass


async def setup(bot: commands.Bot):
    global BOT
    BOT = bot
    await bot.add_cog(Masks())
