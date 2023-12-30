from asyncio import Future

from discord import ButtonStyle, Interaction
from discord.ui import View, button

class ConfirmationView(View):
    """
    View class that allows easy confirm/deny ui.
    Button styles can be overriden in the constructor
    and getting the result of the dialogue is simply 
    done by awaiting the object.
    
    Will raise a TimeoutError on await if the view timed out.
    """
    def __init__(
        self,
        *args,
        confirm_style: ButtonStyle=ButtonStyle.success,
        cancel_style: ButtonStyle=ButtonStyle.danger,
        **kwargs
    ):
        self.__future: Future[bool] = Future()
        super().__init__(*args, **kwargs)
        self._confirm.style = confirm_style
        self._cancel.style = cancel_style
    
    @button(label="Confirm", row=4)
    async def _confirm(self, interaction: Interaction, _):
        await interaction.response.defer()
        self.__future.set_result(True)
        self.stop()
    
    @button(label="Cancel", row=4)
    async def _cancel(self, interaction: Interaction, _):
        await interaction.response.defer()
        self.__future.set_result(False)
        self.stop()
    
    async def on_timeout(self) -> None:
        self.__future.set_exception(TimeoutError("Confirmation timed out"))
        return await super().on_timeout()
    
    def __await__(self):
        return self.__future.__await__()