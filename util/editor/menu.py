from logging import getLogger
from typing import Generic, TypeVar
from discord import SelectOption, ui
import discord
from discord.interactions import Interaction
from util.editor.hierarchy import ChildPage, ParentPage

LOGGER = getLogger("util.editor.menu")

SubmenuPage_co = TypeVar('SubmenuPage_co', bound="SubmenuPage", covariant=True)


class _MenuSelect(ui.Select):
    def __init__(self, editor: "MenuPage", *args, **kwargs):
        self.editor = editor
        super().__init__(*args, **kwargs)
    
    async def callback(self, interaction: Interaction) -> None:
        # TODO: Change the error output on this
        try:
            child_id = int(self.values[0])
        except ValueError:
            LOGGER.error("_MenuSelect value could not be interpreted as integer")
            await interaction.response.send_message(
                "Selected Value is not possible...?",
                ephemeral=True
            )
            return
        try:
            child = next(filter(lambda c: id(c) == child_id, self.editor.CHILDREN))
        except KeyError:
            LOGGER.error("Could not find child for _MenuSelect value %d", child_id)
            await interaction.response.send_message(
                "Could not interpret selected value...",
                ephemeral=True
            )
            return
        
        # Need to defer already because switch_to_child doesn't exit until the child exits.
        await interaction.response.defer()
        await self.editor.switch_to_child(child)


class MenuPage(ParentPage[SubmenuPage_co], Generic[SubmenuPage_co]):
    submenu_placeholder: str|None

    def __init__(self, message: discord.Message|None=None, embed: discord.Embed|None=None):
        super().__init__(message, embed)
        # There's some dark magic going on here.
        # Since the @disable_update decorator isn't applied to _MenuSelect.callback,
        # you might think the callback also executes an editor update afterwards. It does not.
        #
        # Since we initialised _before_ this code here,
        # the wrapper in EditorPage was already called.
        # This means that this component doesn't get wrapped even though it looks like it should.
        # PSA: Don't do this. Always call super().__init__ at the end when working with this.
        #      Otherwise expect your editor updates to be completely insane.
        self.CHILDREN_SELECT = _MenuSelect(
            self,
            placeholder=type(self).submenu_placeholder,
            # Optimises layout to always have back and back to top as lowest row.
            row=3 if isinstance(self, SubmenuPage) else 4,
            options=[
                SelectOption(
                    label=child.name,
                    value=str(id(child)),
                    description=child.description,
                    emoji=child.emoji
                )
                for child in type(self).CHILDREN
            ]
        )
        self.add_item(self.CHILDREN_SELECT)

    def __init_subclass__(
        cls,
        *,
        timeout: float|None=180,
        resets_message_content: bool=False,
        submenu_placeholder: str|None
    ) -> None:
        cls.submenu_placeholder = submenu_placeholder

        return super().__init_subclass__(
            timeout=timeout,
            resets_message_content=resets_message_content
        )


class SubmenuPage(ChildPage):
    name: str
    description: str|None
    emoji: discord.Emoji|discord.PartialEmoji|str|None

    def __init_subclass__(
        cls,
        *,
        timeout: float|None=180,
        resets_message_content: bool=False,
        name: str|None=None,
        description: str|None=None,
        emoji: discord.Emoji|discord.PartialEmoji|str|None=None
    ) -> None:
        cls.name = name if name is not None else cls.__name__
        cls.description = description
        cls.emoji = emoji
        return super().__init_subclass__(
            timeout=timeout,
            resets_message_content=resets_message_content
        )
    
    @discord.ui.button(label="Back", row=4)
    async def _back_to_parent(self, interaction: discord.Interaction, _):
        await interaction.response.defer()
        await self.switch_to_parent()
    
    @discord.ui.button(label="Back to top", row=4)
    async def _back_to_top(self, interaction: discord.Interaction, _):
        await interaction.response.defer()
        # Inverse hierarchy traversal
        # Algorithmical but can be done synchronously, because it takes no time at all.
        # Seriously: If your menu tree is large enough to demand this in an executor,
        # you need to re(de)sign.
        root = self.parent
        while isinstance(root, ChildPage):
            root = root.parent
        
        await self.switch(root)
