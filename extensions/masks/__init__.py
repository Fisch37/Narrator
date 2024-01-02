import asyncio
from logging import getLogger
from io import BytesIO

import discord
from discord.ext import commands
from discord import app_commands
from discord.utils import MISSING
from pydantic import ValidationError

from data.sql.ormclasses import Mask
from extensions.masks.mask_apply import AppliedMaskManager, ChannelOrThread, MaskMessageEditModal, MessageCache
from extensions.masks.mask_editor import EditCollisionError, MaskCreatorModal, MaskEditor
from extensions.masks.mask_show import PrivateShowView, mask_to_embed, summon_all_public_show_views
from extensions.masks.mask_serialiser import (
    serialize as mask_serialize,
    deserialize as mask_deserialize
)
from extensions.masks.mask_transformer import MaskParameter, MaskTransformer
from util.confirmation_view import ConfirmationView
from util.coroutine_tools import may_fetch_member
from util.webhook_pool import SupportsWebhooks, WebhookPool

LOGGER = getLogger("extensions.masks")
BOT: commands.Bot


class Masks(commands.Cog):
    CACHE_LIFETIME_MINS = 15
    
    def __init__(self) -> None:
        self.application_manager = AppliedMaskManager()
        self.webhook_pool = WebhookPool(BOT)
        self.mask_message_cache = MessageCache(lifetime=self.CACHE_LIFETIME_MINS)
        self.mask_message_edit_menu = app_commands.ContextMenu(
            name="Edit Message",
            callback=self.mask_message_edit
        )
        self.mask_message_delete_menu = app_commands.ContextMenu(
            name="Delete Message",
            callback=self.mask_message_delete
        )
        BOT.tree.add_command(self.mask_message_edit_menu)
        BOT.tree.add_command(self.mask_message_delete_menu)
        super().__init__()
    
    async def _summon_public_views_stored(self):
        # FIXME: Persistent views created here don't respond to interactions
        self._public_show_views = await summon_all_public_show_views(BOT)
        for view in self._public_show_views:
            BOT.add_view(view)
        pass
    
    async def cog_load(self) -> None:
        asyncio.create_task(self._summon_public_views_stored())
        asyncio.create_task(self.application_manager.fetch_all())
        return await super().cog_load()
    
    mask = app_commands.Group(
        name="mask",
        description="Management command for use of masks.",
        default_permissions=None,
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
            return
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
            # ("" or None) == None. This makes some degree of sense, but it's grey magic.
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
    
    @mask.command(
        name="apply",
        description="Set a mask or disable them to use for the selected channel"
    )
    @app_commands.describe(
        mask="The mask to apply in the selected channel. Leave unset to disable masks for this channel.",
        channel="The channel to apply the mask in. If left unset, uses the current channel.",
        include_subchannels="If enabled (the default) applies the passed mask for all subchannels as well."
    )
    async def apply_mask(
        self,
        interaction: discord.Interaction,
        mask: MaskParameter|None=None,
        channel: ChannelOrThread|None=None,
        include_subchannels: bool=True
    ):
        if channel is None:
            # Interaction channel can never be private because /mask is guild only
            # Not sure when interaction channel could be None though...
            channel = interaction.channel
        
        app = await self.application_manager.set(
            mask,
            interaction.user,
            channel,
            include_subchannels
        )
        await interaction.response.send_message(
            f"{mask.name} has been set as your mask for {channel.mention}!",
            embed=await app.to_embed(BOT),
            ephemeral=True
        )
    
    @mask.command(
        name="detach",
        description="Remove mask application from a specified channel"
    )
    @app_commands.describe(
        channel="The channel to target"
    )
    async def detach_mask(
        self,
        interaction: discord.Interaction,
        channel: ChannelOrThread|None=None
    ):
        if channel is None:
            channel = interaction.channel
        app = await self.application_manager.hierarchical(interaction.user, channel)
        if app is None:
            await interaction.response.send_message(
                ":x: There is no mask applied for this channel!",
                ephemeral=True
            )
            return
        await self.application_manager.remove(
            interaction.user,
            app.channel_id
        )
        true_channel = await app.may_fetch_channel(BOT)
        await interaction.response.send_message(
            f"Detached mask {app.mask.name} from channel {true_channel.mention}.",
            ephemeral=True
        )
    
    @mask.command(
        name="reveal",
        description="Show the mask applied in the selected channel"
    )
    @app_commands.describe(
        channel="The channel to target. If unset, uses the current channel."
    )
    async def reveal_mask(
        self,
        interaction: discord.Interaction,
        channel: ChannelOrThread|None=None
    ):
        if channel is None:
            channel = interaction.channel
        app = await self.application_manager.hierarchical(interaction.user, channel)
        if app is None:
            await interaction.response.send_message(
                f"There is no mask applied in {channel.mention}",
                ephemeral=True
            )
        else:
            await interaction.response.send_message(
                embed=await app.to_embed(BOT),
                ephemeral=True
            )
    
    @mask.command(
        name="export",
        description="Export a mask into a single file for easy transfer."
    )
    async def export_mask(
        self,
        interaction: discord.Interaction,
        mask: MaskParameter
    ):
        loop = asyncio.get_running_loop()
        await interaction.response.defer(ephemeral=True)
        serialized = await loop.run_in_executor(None, mask_serialize, mask)
        # FIXME: This sanitisation might not fully encompass all illegal characters.
        sanitized_mask_name = (
            mask.name.encode("ascii", "ignore")
            .decode("ascii")
        )
        await interaction.followup.send(
            f"We've turned {mask.name} into a little puppet for you!",
            file=discord.File(
                BytesIO(serialized.encode("utf-8")),
                filename="mask_" + sanitized_mask_name + ".json"
            ),
            ephemeral=True
        )
    
    @mask.command(
        name="import",
        description="Import a mask from a JSON file"
    )
    async def import_mask(
        self,
        interaction: discord.Interaction,
        file: discord.Attachment
    ):
        # TODO: Write this into a config entry
        # Unfortunately the config is inaccessible ouside main right now
        if file.size > 1024**2:
            # Sanity. This bot is not designed for public use,
            # but I'd still like to keep my internet connection, thank you very much.
            await interaction.response.send_message(
                ":x: Woah, now _that's_ a character sheet! (Puppet file too large)",
                ephemeral=True
            )
            return
        raw_content = await file.read()
        await interaction.response.defer(ephemeral=True)
        loop = asyncio.get_running_loop()
        try:
            mask = await loop.run_in_executor(
                None,
                mask_deserialize,
                raw_content.decode("utf-8")
            )
        except UnicodeDecodeError:
            await interaction.followup.send(
                ":x: What kind of language is that?! (Invalid characters in file)",
                ephemeral=True
            )
        except ValidationError:
            await interaction.followup.send(
                ":x: Now that doesn't look like something I'd write...\
                Are you... trying to trick me? (Puppet file is not valid)",
                ephemeral=True
            )
        else:
            # It's weird that these values can be None even when I wrap things in a dataclass,
            # but it's handy here.
            mask.owner_id = interaction.user.id
            mask.guild_id = interaction.guild.id
            # "update" the mask. We all know what this really does
            await mask.update()
            await interaction.followup.send(
                f"Animated puppet of {mask.name}!",
                embed=await mask.to_embed(BOT),
                ephemeral=True
            )
    
    @edit_mask.error
    @mask_remove.error
    @mask_show.error
    @apply_mask.error
    @export_mask.error
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
            # Monkey patching is fun, isn't it!
            # Yeah, we need this so that the general error handler doesn't scream
            error.is_handled = True # type: ignore
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
    
    async def _webhook_message_from_message(
        self,
        message: discord.Message
    ) -> discord.WebhookMessage:
        channel_or_thread = message.channel
        if isinstance(channel_or_thread, discord.Thread):
            channel = channel_or_thread.parent
            thread = channel_or_thread
        else:
            channel = channel_or_thread
            thread = MISSING
        webhook = await self.webhook_pool.get(
            channel,
            reason="Some reason... This should never happen"
        )
        return await webhook.fetch_message(message.id, thread=thread)
    
    async def _check_mask_message(
        self,
        interaction: discord.Interaction,
        message: discord.Message
    ) -> discord.Member|None:
        try:
            member = self.mask_message_cache[message]
        except KeyError:
            await interaction.response.send_message(
                "This message is not a Mask message or has been for a long time.",
                ephemeral=True
            )
            return None
        if interaction.user != member:
            await interaction.response.send_message(
                "You do not have permission to change this message.",
                ephemeral=True
            )
            return None
        return member
    
    # This is a ContextMenu command. See __init__
    async def mask_message_edit(
        self,
        interaction: discord.Interaction,
        message: discord.Message
    ):
        member = await self._check_mask_message(interaction, message)
        if member is None:
            return
        
        modal = MaskMessageEditModal()
        modal.content.default = message.content
        await interaction.response.send_modal(modal)
        if await modal.wait():
            return
        
        webhook_message = await self._webhook_message_from_message(message)
        await webhook_message.edit(content=modal.content.value)
    
    async def mask_message_delete(
        self,
        interaction: discord.Interaction,
        message: discord.Message
    ):
        member = await self._check_mask_message(interaction, message)
        if member is None:
            return
        
        confirm_view = ConfirmationView(
            confirm_style=discord.ButtonStyle.danger,
            cancel_style=discord.ButtonStyle.success
        )
        await interaction.response.send_message(
            "Are you sure you want to delete this message?",
            view=confirm_view,
            ephemeral=True
        )
        should_delete = await confirm_view
        if not should_delete:
            await interaction.edit_original_response(
                content="Deletion cancelled.",
                view=None
            )
            return
        webhook_message = await self._webhook_message_from_message(message)
        await webhook_message.delete()
        await interaction.edit_original_response(
            content="Message deleted!",
            view=None
        )
    
    
    @commands.Cog.listener("on_message")
    async def handle_mask_messages(self, message: discord.Message):
        if (
            message.guild is None
            or message.author.bot
            or message.content.startswith("//")
        ):
            # Don't consider DM messages
            # Don't consider Bots
            # Don't replace messages starting with //
            return
        channel: SupportsWebhooks|discord.Thread = message.channel
        app = await self.application_manager.hierarchical(message.author, channel)
        if app is None:
            # No applied mask, means no action
            return
        mask = app.mask
        if mask is None:
            # Specifically blocking out masks
            return
        
        if isinstance(channel, discord.Thread):
            non_thread_channel = channel.parent
        else:
            non_thread_channel = channel
        if non_thread_channel is None:
            await message.channel.send(
                "Oh no! Couldn't send mask imitation: Thread parent is None"
            )
            LOGGER.error(f"Thread parent is None in {channel.id}")
            return
        webhook = await self.webhook_pool.get(
            non_thread_channel,
            reason="Mask send required new webhook"
        )
        mask_message = await webhook.send(
            content=message.content,
            username=mask.name,
            avatar_url=mask.avatar_url or message.author.display_avatar.url,
            tts=message.tts,
            embeds=message.embeds,
            allowed_mentions=discord.AllowedMentions.none(),  # First message already mentions
            thread=channel if isinstance(channel, discord.Thread) else MISSING,
            silent=True,  # First message already provides notifications
            wait=True
        )
        self.mask_message_cache.push(mask_message, message.author)
        if len(message.attachments) > 0:
            # TODO: Figure it whether we want to do attachments
            return
        try:
            await message.delete()
        except discord.errors.NotFound:
            # The audacity!
            pass
        except discord.errors.Forbidden:
            await message.channel.send(
                "Woops! Seems I'm not allowed to delete messages around here. \
                Please fix :pleading_face:"
            )


async def setup(bot: commands.Bot):
    global BOT
    BOT = bot
    await bot.add_cog(Masks())
