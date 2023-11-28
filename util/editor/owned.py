import discord
from util.editor.base import EditorPage


class OwnedEditor(EditorPage):
    """
    Editor superclass that requires an owner to be registered for objects of this class.
    The owner should not change within the object's lifetime.
    """
    def __init__(
        self,
        message: discord.Message|None=None,
        embed: discord.Embed|None=None,
        *,
        owner: discord.Member
    ):
        self._owner = owner
        super().__init__(message, embed)
    
    @property
    def owner(self) -> discord.Member:
        """The member that owns this editor"""
        return self._owner
