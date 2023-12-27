import asyncio
from collections.abc import Callable, Coroutine
from logging import getLogger
from typing import Any, Literal, NamedTuple

import discord
from discord import ButtonStyle, ui
from sqlalchemy.ext.asyncio import AsyncSession

from data.sql.ormclasses import Mask, MaskField
from util.auto_stop_modal import AutoStopModal
from util.editor import SwitchablePage, OwnedEditor
from util.editor.base import disable_update
from util.editor.closable import ClosableEditor

EMBED_MAX_TITLE_LENGTH = 256
LOGGER = getLogger("extensions.masks.editors")
MISSING = object()

MODAL_TITLE_MAX_LENGTH = 45

def _cap_str(string: str, length: int=100) -> str:
    if len(string) <= length:
        return string
    else:
        return string[:length-3] + "..."


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
        self._selected: Mask|None
        super().__init__(
            message,
            embed or discord.Embed(),
            owner=owner
        )
        for mask in owner_masks:
            self.select_mask.append_option(discord.SelectOption(
                label=mask.name,
                value=str(mask.id),
                description=_cap_str(mask.description)
            ))

    @ui.select(placeholder="Select a mask...")
    @disable_update(disable_message_update=True)
    async def select_mask(self, interaction: discord.Interaction, select: ui.Select):
        mask_id = int(select.values[0])
        self._selected = next(filter(lambda mask: mask.id == mask_id, self._owner_masks))
        await interaction.response.defer()
        self.stop()
    
    @property
    def selected(self) -> Mask|None:
        return self._selected


class FieldSelector(discord.ui.View):
    FieldSelectCallback = Callable[
        [discord.Interaction, "FieldSelector"],
        Coroutine[Any, Any, Any]
    ]
    
    def __init__(
        self,
        mask: Mask,
        *,
        timeout: float | None = 180,
        auto_defer: bool=True,
        custom_placeholder: str|None=MISSING
    ):
        self.mask = mask
        self.auto_defer = auto_defer
        self._future: asyncio.Future[discord.Interaction] = asyncio.Future()
        super().__init__(timeout=timeout)
        for i, field in enumerate(self.mask.fields):
            self.field_select.append_option(discord.SelectOption(
                label=field.name,
                value=str(i),
                description=_cap_str(field.value)
            ))
        if custom_placeholder is not MISSING:
            self.field_select.placeholder = custom_placeholder
    
    async def on_timeout(self) -> None:
        self._future.set_exception(TimeoutError)
        return await super().on_timeout()
    
    @ui.select(placeholder="Select a field...")
    async def field_select(self, interaction: discord.Interaction, select: ui.Select):
        self.stop()
        if self.auto_defer:
            await interaction.response.defer()
        self._future.set_result(interaction)
    
    @property
    def selected_index(self) -> int:
        return int(self.field_select.values[0])
    
    def __await__(self):
        return self._future.__await__()


class FieldEditModal(AutoStopModal):
    class _FieldData(NamedTuple):
        name: str
        value: str
        inline: bool
    
    name = ui.TextInput(
        label="Title",
        max_length=256
    )
    value = ui.TextInput(
        label="Content",
        style=discord.TextStyle.long,
        max_length=1024
    )
    on_seperate_line = ui.TextInput(
        label="Seperate Line?",
        placeholder="Write something here to have the field on a seperate line",
        required=False,
        max_length=1
    )
    
    @property
    def results(self) -> _FieldData:
        return type(self)._FieldData(
            self.name.value,
            self.value.value,
            not bool(self.on_seperate_line.value)
        )

class FieldPositionModal(AutoStopModal):
    position_input = ui.TextInput(
        label="Position",
        placeholder="Leave unset to append.",
        required=False,
        max_length=2,
        default="-1"
    )
    
    def __init__(self, *args, **kwargs) -> None:
        self._position: int = -1
        self._exception: ValueError|None=None
        super().__init__(*args, **kwargs)
    
    async def on_submit(self, *args, **kwargs):
        # Parsing at this point to prevent exceptions in properties
        # Should I have just made .position a method? Probably.
        try:
            self._position = int(self.position_input.value)
            if self._position < -1: # -1 means append. Doesn't make sense for inserts though
                raise ValueError("Position cannot be negative")
        except ValueError as e:
            self._exception = e
        await super().on_submit(*args, **kwargs)
    
    async def wait(self) -> bool:
        res = await super().wait()
        if not res and self._exception:
            raise self._exception
        return res
    
    @property
    def position(self) -> int:
        return self._position


class FieldCreateModal(FieldPositionModal, FieldEditModal): ...


class FieldMoveView(ui.View):
    """
    Ui for moving an embed field around.
    """
    def __init__(
        self,
        editor: "MaskEditor",
        target_index: int,
        *,
        timeout: float|None=180
    ):
        self.editor = editor
        self._target_index = target_index
        super().__init__(timeout=timeout)
    
    @property
    def mask(self) -> Mask:
        return self.editor.mask
    
    @property
    def fields(self):
        return self.mask.fields
    
    async def _update(self):
        self.to_first.disabled = self.backward.disabled = self._target_index == 0
        self.to_last.disabled = self.forward.disabled = self._target_index == (len(self.fields) - 1)
        await self.editor.update()
        await self.editor.message.edit(view=self, embed=self.editor.embed)
    
    def _pop_current(self):
        return self.fields.pop(self._target_index)
    
    @ui.button(label="First", emoji="\u23EA", style=ButtonStyle.green, row=0)
    async def to_first(self, interaction: discord.Interaction, _):
        self.fields.insert(
            0,
            self._pop_current()
        )
        self._target_index = 0
        await self._update()
        await interaction.response.defer()
    
    @ui.button(label="Backward", emoji="\u25C0", style=ButtonStyle.primary, row=0)
    async def backward(self, interaction: discord.Interaction, _):
        self.fields.insert(
            self._target_index - 1,
            self._pop_current()
        )
        self._target_index -= 1
        await self._update()
        await interaction.response.defer()
    
    @ui.button(label="Forward", emoji="\u25B6", style=ButtonStyle.secondary, row=0)
    async def forward(self, interaction: discord.Interaction, _):
        self.fields.insert(
            self._target_index + 1,
            self._pop_current()
        )
        self._target_index += 1
        await self._update()
        await interaction.response.defer()
    
    @ui.button(label="Last", emoji="\u23ED", style=ButtonStyle.red, row=0)
    async def to_last(self, interaction: discord.Interaction, _):
        self.fields.append(
            self._pop_current()
        )
        self._target_index = len(self.fields) - 1
        await self._update()
        await interaction.response.defer()
    
    @ui.button(label="Done", style=ButtonStyle.success, row=1)
    async def close(self, interaction: discord.Interaction, _):
        await interaction.response.defer()
        self.stop()


class MaskEditor(ClosableEditor, OwnedEditor):
    """This editor allows modifying the selected mask"""
    def __init__(
        self,
        message: discord.Message|None=None,
        embed: discord.Embed|None=None,
        *,
        owner: discord.Member,
        mask: Mask,
        session: AsyncSession|None=None
    ):
        self.mask = mask
        self.embed: discord.Embed
        self.session = session
        super().__init__(message, embed or discord.Embed(), owner=owner)

    async def update(self):
        # Disallow operations when there are no fields
        self.remove_field.disabled = self.move_field.disabled = len(self.mask.fields) < 1
        
        self.embed.title = self.mask.name
        self.embed.description = self.mask.description
        self.embed.set_image(
            url=self.mask.avatar_url
        ).set_author(
            name=self.owner.display_name,
            icon_url=self.owner.display_avatar.url
        )
        self.embed.clear_fields()
        for field in self.mask.fields:
            self.embed.add_field(
                name=field.name,
                value=field.value,
                inline=field.inline
            )
        await super().update()
    
    async def on_end(self) -> None:
        if self.message is None:
            LOGGER.error("MaskEditor ended without ever having a message!")
        await self.message.edit(content="```\nThis editor has ended.```", view=None)

    @ui.button(label="Edit Info", row=0)
    async def edit_info(self, interaction: discord.Interaction, _):
        modal = MaskCreatorModal(f"Editing {self.mask.name}")
        modal.name.default = self.mask.name
        modal.description.default = self.mask.description
        modal.avatar_url.default = self.mask.avatar_url

        await interaction.response.send_modal(modal)
        if await modal.wait(): return
        self.mask.name = modal.name.value
        self.mask.description = modal.description.value
        self.mask.avatar_url = modal.avatar_url.value or None  # "" -> None

    @ui.button(label="Add Field", row=1, style=discord.ButtonStyle.success)
    async def add_field(self, interaction: discord.Interaction, _):
        modal = FieldCreateModal(title="Add a new field")
        await interaction.response.send_modal(modal)
        try:
            if await modal.wait():
                return
        except ValueError:
            await interaction.followup.send(
                "You did not provide a valid position. \
                For your peace of mind, here is your data:",
                embed=discord.Embed(
                    title="Modal Input",
                    description=f"Line Seperation: `{modal.on_seperate_line.value}`"
                ).add_field(
                    name=modal.results.name,
                    value=modal.results.value,
                ),
                ephemeral=True
            )
            return
        field = MaskField(*modal.results)
        if modal.position == -1:
            self.mask.fields.append(field)
        else:
            self.mask.fields.insert(modal.position, field)
    
    async def _sequenced_selector(
        self,
        interaction: discord.Interaction,
        *,
        custom_placeholder: str|None=MISSING
    ) -> tuple[discord.Interaction, FieldSelector]:
        """
        Shorthand to select an embed field and return the finishing interaction.
        Raises timeout error when the view times out.
        """
        selector_view = FieldSelector(
            self.mask,
            auto_defer=False,
            custom_placeholder=custom_placeholder
        )
        await interaction.response.defer()
        await self.message.edit(view=selector_view)
        return await selector_view, selector_view
    
    @ui.button(label="Edit Field", row=1, style=discord.ButtonStyle.primary)
    async def edit_field(self, interaction: discord.Interaction, _):
        try:
            inner_interaction, selector = await self._sequenced_selector(interaction)
        except TimeoutError:
            return
        
        field = self.mask.fields[selector.selected_index]
        modal = FieldEditModal(
            title=_cap_str(
                f'Editing {field.name}',
                MODAL_TITLE_MAX_LENGTH
            )
        )
        modal.name.default = field.name
        modal.value.default = field.value
        modal.on_seperate_line.default = "!" if not field.inline else ""
        
        await inner_interaction.response.send_modal(modal)
        await modal.wait()
        (
            field.name,
            field.value,
            field.inline
        ) = modal.results
        await self.mask.update(session=self.session)
    
    @ui.button(label="Move Field", row=1, style=discord.ButtonStyle.secondary)
    async def move_field(self, interaction: discord.Interaction, _):
        target_selector = FieldSelector(
            self.mask,
            custom_placeholder="Select a field to move..."
        )
        await interaction.response.defer()
        await self.message.edit(view=target_selector)
        if await target_selector.wait():
            return
        
        # FIXME: This is a race condition since there is no editor lock on masks.
        move_view = FieldMoveView(
            self,
            target_selector.selected_index
        )
        await self.message.edit(view=move_view)
        if await move_view.wait():
            return
        await self.mask.update(session=self.session)
    
    @ui.button(label="Remove Field", row=1, style=discord.ButtonStyle.danger)
    async def remove_field(self, interaction: discord.Interaction, _):
        selector = FieldSelector(self.mask)
        await self.message.edit(view=selector)
        await interaction.response.defer()
        if await selector.wait():
            return
        # Hello! This will cause problems if there can be two of 
        # these editors targeting the same mask at the same time!
        # TODO: Do I care? Maybe later!
        self.mask.fields.pop(selector.selected_index)
        await self.mask.update(session=self.session)


class MaskCreatorModal(ui.Modal):
    def __init__(self, title: str="Create a mask"):
        super().__init__(timeout=None, title=title)

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
