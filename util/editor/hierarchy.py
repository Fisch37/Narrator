from typing import Generic, TypeVar
import discord
from util.editor.base import EditorPage

SwitchablePage_co = TypeVar('SwitchablePage_co', bound="SwitchablePage")
ChildPage_co = TypeVar('ChildPage_co', bound="ChildPage")


class SwitchablePage(EditorPage):
    async def switch(
        self,
        new_editor: "SwitchablePage_co"|"type[SwitchablePage_co]"
    ) -> SwitchablePage_co:
        if isinstance(new_editor, type):
            editor_object = new_editor(self.message, self.embed)
        else:
            editor_object = new_editor
        await editor_object.update()
        await editor_object.update_message()
        return editor_object


class ChildPage(SwitchablePage):
    def __init__(
        self,
        message: discord.Message|None=None,
        embed: discord.Embed|None=None,
        *,
        parent: "ParentPage"
    ):
        self.parent = parent
        super().__init__(message, embed)
    
    async def switch_to_parent(self):
        await self.switch(self.parent)


class ParentPage(SwitchablePage, Generic[ChildPage_co]):
    CHILDREN: tuple[type[ChildPage_co], ...]

    def __init__(self, message: discord.Message|None=None, embed: discord.Embed|None=None):
        self._child_instances: dict[type[ChildPage_co], ChildPage_co] = {}
        super().__init__(message, embed)
    
    async def switch_to_child(self, child_type: type[ChildPage_co]) -> ChildPage_co:
        try:
            child_object = self._child_instances[child_type]
        except KeyError:
            child_object = child_type(self.message, self.embed, parent=self)
        await self.switch(child_object)
        return child_object
