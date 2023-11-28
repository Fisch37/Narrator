import discord
from discord import ui
from data.sql.ormclasses import Mask
from util.editor import SwitchablePage, OwnedEditor
from util.editor.base import disable_update

EMBED_MAX_TITLE_LENGTH = 256


class MaskSelector(OwnedEditor, SwitchablePage):
    def __init__(
        self,
        message: discord.Message|None=None,
        embed: discord.Embed|None=None,
        *,
        owner: discord.Member,
        owner_masks: list[Mask]
    ):
        self.embed: discord.Embed
        self._owner_masks = owner_masks
        super().__init__(
            message,
            embed or discord.Embed(),
            owner=owner
        )
        for mask in owner_masks:
            self.select_mask.append_option(discord.SelectOption(
                label=mask.name,
                value=str(mask.id),
                description=(
                    mask.description
                    if len(mask.description) <= 100
                    else mask.description[:97] + "..."
                )
            ))

    async def update(self):
        self.embed.clear_fields()
        self.embed

    @ui.select(placeholder="Select a mask...")
    @disable_update(disable_message_update=True)
    async def select_mask(self, interaction: discord.Interaction, select: ui.Select):
        mask_id = int(select.values[0])
        mask = next(filter(lambda mask: mask.id == mask_id, self._owner_masks))
        await interaction.response.defer()
        await self.switch(MaskEditor(
            self.message,
            self.embed,
            owner=self.owner,
            mask=mask
        ))


class MaskEditor(OwnedEditor):
    """This editor allows modifying the selected mask"""
    def __init__(
        self,
        message: discord.Message|None=None,
        embed: discord.Embed|None=None,
        *,
        owner: discord.Member,
        mask: Mask
    ):
        self.mask = mask
        super().__init__(message, embed, owner=owner)


class MaskCreatorModal(ui.Modal, title="Create a mask"):
    def __init__(self):
        super().__init__(timeout=None)

    name = ui.TextInput(label="Name", max_length=EMBED_MAX_TITLE_LENGTH)
    description = ui.TextInput(
        label="Description",
        style=discord.TextStyle.long,
        placeholder="Enter your character's description here...",
        required=False
    )
    avatar_url = ui.TextInput(
        label="Picture URL",
        placeholder="Enter the URL to your character's picture (if wanted)",
        required=False
    )

    async def on_submit(self, interaction: discord.Interaction) -> None:
        await interaction.response.defer()
