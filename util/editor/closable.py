import asyncio
import discord, discord.ui

from util.auto_stop_modal import AutoStopModal
from util.editor import EditorPage
from util.editor.base import disable_update

class _ClosingModal(AutoStopModal, title="Close this editor?"):
    # This dummy field feels stupid, but I think it's better 
    dummy_field = discord.ui.TextInput(
        label="Ignore me",
        placeholder="Leave an emoji, if you wish :wink:",
        required=False,
        max_length=30
    )


class ClosableEditor(EditorPage):
    """
    Subclass of EditorPage that adds a "Close" button into the last view row.
    Subclasses may override the existing `ClosableEditor.on_close` 
    method to implement custom closing interactions.
    
    Implements a custom `await` syntax that ensures on_end finishes.
    """
    _close_timeout_message: str
    
    def __init__(self, *args, **kwargs):
        self.__ending_task: asyncio.Task|None = None
        super().__init__(*args, **kwargs)
    
    def __init_subclass__(cls, *, close_timeout_message: str|None=None, **kwargs) -> None:
        if close_timeout_message is None:
            close_timeout_message = ":sleeping: Modal timed out"
        cls._close_timeout_message = close_timeout_message
        return super().__init_subclass__(**kwargs)
    
    async def on_close(self, interaction: discord.Interaction) -> None:
        """
        This method is called when the editor closes without timing out.
        By default this method does nothing. 
        Consider overriding this method to implement custom closing behaviour.
        
        Note that this method is called _before_ the editor is actually stopped.
        """
    
    async def on_end(self) -> None:
        """
        This method is called when the editor ends, regardless of whether it timed out.
        By default this method removes the editor from the editor message, leaving it unchanged.
        Consider overriding this method for finalising.
        """
    
    async def on_timeout(self) -> None:
        await self.on_end()
        return await super().on_timeout()
    
    @discord.ui.button(label="Close", style=discord.ButtonStyle.danger, row=4)
    # closing interactions shouldn't update by default as that may interfere with on_close.
    @disable_update(disable_update=True, disable_message_update=True)
    async def _close_interaction(self, interaction: discord.Interaction, _):
        modal = _ClosingModal()
        await interaction.response.send_modal(modal)
        if await modal.wait():
            await interaction.followup.send(
                type(self)._close_timeout_message,
                ephemeral=True
            )
            return True
        
        await self.on_close(interaction)
        self.stop()
    
    def stop(self) -> None:
        # Allows on_end to be async which is expected to be the common case
        self.__ending_task = asyncio.create_task(self.on_end())
        return super().stop()
    
    def __await__(self):
        if self.__ending_task is not None:
            return self.__ending_task.__await__()
        return _never_generator()


def _never_generator():
    # The entire purpose of this generator function is to perform dark magic upon __await__.
    # This function returns a generator that holds no items and allows ClosableEditor.__await__
    # to function properly. Writing some code like
    # yield from ()
    # return
    # in __await__ would break the if-branch of the program, 
    # not using any yield would make it a sometimes-generator function.
    # Needless to say: Removing this function is probably impossible and, honestly, 
    # you should not look at it too hard.
    yield from ()
