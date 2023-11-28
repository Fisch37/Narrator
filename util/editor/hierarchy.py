from typing import Generic, TypeVar
import discord
from util.editor.base import EditorPage

SwitchablePage_co = TypeVar('SwitchablePage_co', bound="SwitchablePage", covariant=True)
ChildPage_co = TypeVar('ChildPage_co', bound="ChildPage", covariant=True)


class SwitchablePage(EditorPage):
    """
    A subclass of `EditorPage` that includes switching behaviour.
    Implements a new asynchronous method `switch` that allows seamless
    swapping of the editors.

    It should be noted that every switch will add to the call stack.
    """
    async def switch(
        self,
        new_editor
    ) -> SwitchablePage_co:
        """
        Switches to the passed editor.
        May receive an object or a type at which point it initialise a new object.

        Returns the editor instance (newly created or not) after said editor closes.

        Beware that your code may cause editor updates after the switch has returned.
        This is not advised as it can lead to unexpected UI changes.
        """
        if isinstance(new_editor, type):
            editor_object = new_editor(self.message, self.embed)
        else:
            editor_object = new_editor
        await editor_object.update()
        await editor_object.update_message()
        return editor_object


class ChildPage(SwitchablePage):
    """
    This switchable editor is designed to work as a child to a ParentPage class.
    It requires the existence of a parent.
    References to its parent are only stored on instantiation.
    """
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
        """
        Performs a switch to this editor's parent.
        """
        await self.switch(self.parent)


class ParentPage(SwitchablePage, Generic[ChildPage_co]):
    """
    This class allows for child editors.
    The children of the editor must be defined as a tuple in the `CHILDRENS` class constant.
    A method `switch_to_child` also allows performing a fluent switch to a child object.

    Children are stored by their class by default and are instantiated lazily with a cache.
    Once a child of a certain type has been instantiated it won't be again within this instance.
    """
    CHILDREN: tuple[type[ChildPage_co], ...]

    def __init__(self, message: discord.Message|None=None, embed: discord.Embed|None=None):
        self._child_instances: dict[type[ChildPage_co], ChildPage_co] = {}
        super().__init__(message, embed)
    
    async def switch_to_child(self, child_type: type[ChildPage_co]) -> ChildPage_co:  # type: ignore
        """
        Fluently switches to a child of this editor.
        Children may be pulled from cache or instantiated at runtime.

        Returns the child editor.
        """
        child_object = self.get_child(child_type)
        await self.switch(child_object)
        return child_object
    
    def get_child(self, child_type: type[ChildPage_co]) -> ChildPage_co:  # type: ignore
        """
        Gets an instance of the passed child type.
        This method tries to pull from cache, when possible.

        Raises `KeyError` when the passed type is not a child of this editor.
        """
        if child_type not in type(self).CHILDREN:
            raise KeyError(f"Type {child_type} is not a part of {type(self)}")
        try:
            return self._child_instances[child_type]
        except KeyError:
            return child_type(self.message, self.embed, parent=self)
