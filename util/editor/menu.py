import discord
from util.editor.base import EditorPage


class ChildPage(EditorPage):
    def __init__(
        self,
        message: discord.Message|None=None,
        embed: discord.Embed|None=None,
        *,
        parent: "ParentPage"
    ):
        self.parent = parent
        super().__init__(message, embed)
    
    async def to_parent(self):
        raise NotImplementedError
