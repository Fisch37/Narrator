from inspect import iscoroutinefunction
from typing import Any, Callable, Coroutine, Generic, TypeVar, TypeVarTuple
from logging import getLogger
from discord import ui
import discord

LOGGER = getLogger("util.editor.base")

MAXIMUM_ROW_CONTENT = 5
MAXIMUM_ROW_WITH_SELECT = 1
MAXIMUM_ROW_COUNT = 5

Ts = TypeVarTuple('Ts')
T = TypeVar('T')


class EditorPage(ui.View):
    """
    This class represents a single menu for an editor.
    It inherits from `discord.ui.View`.
    An editor page also keeps reference to a message which is where it appears as a View object.
    """
    timeout: float|None

    def __init__(
        self,
        message: discord.Message|None=None,
        embed: discord.Embed|None=None
    ):
        self.message = message
        self.embed = embed
        super().__init__(timeout=type(self).timeout)
    
    def __init_subclass__(cls, *, timeout: float|None=180) -> None:
        cls.timeout = timeout

        return super().__init_subclass__()
    
    async def update(self): ...
    
    async def update_message(self):
        if self.message is None:
            LOGGER.warn("EditorPage.update_message called without set message!")
            return
        await self.message.edit(embed=self.embed, view=self)
    
    async def set_component_state(self, state: bool):
        for item in self.children:
            item.disabled = state  # type: ignore
        await self.update_message()


class disable_when_processing(Generic[T, *Ts]):
    def __init__(self, func: Callable[["EditorPage", *Ts], Coroutine[Any, Any, T]]):
        if not iscoroutinefunction(func):
            raise ValueError("disable_when_processing decorator requires coroutine function!")
        self.func = func
        self.disabled_items = []
        self.editor: "EditorPage"
    
    async def __call__(self, editor: "EditorPage", *args: *Ts, **kwargs) -> T:
        self.editor = editor
        async with self:
            return await self.func(editor, *args, **kwargs)
    
    async def __aenter__(self) -> None:
        # Every possible item that we care about has a disabled attribute.
        # Not ui.Item itself though because weirdness.
        for item in self.editor.children:
            if not item.disabled:  # type: ignore
                # Stores a reference to all items that were disabled by this context manager
                # Storing these allows the user to disable components manually
                # and for us to preserve these changes.
                # This does not allow inner functions to disable items however.
                self.disabled_items.append(item)
            item.disabled = True  # type: ignore
        await self.editor.update_message()

    async def __aexit__(self, exc, exc_type, traceback) -> None:
        for item in self.disabled_items:
            item.disabled = False
        self.disabled_items.clear()
        await self.editor.update_message()
