from inspect import iscoroutinefunction
from typing import Any, Callable, Coroutine, Generic, ParamSpec, TypeVar, TypeVarTuple
from logging import getLogger
from discord import ui
from discord.utils import MISSING
import functools
import discord

LOGGER = getLogger("util.editor.base")

MAXIMUM_ROW_CONTENT = 5
MAXIMUM_ROW_WITH_SELECT = 1
MAXIMUM_ROW_COUNT = 5

Ts = TypeVarTuple('Ts')
T = TypeVar('T')
P = ParamSpec('P')
GenericCoroutineFunction = Callable[P, Coroutine[Any, Any, T]]


def _wraps_update(
    editor: "EditorPage",
    func: GenericCoroutineFunction
) -> GenericCoroutineFunction:
    @functools.wraps(func)
    async def wrapper(*args, **kwargs):
        response = await func(*args, **kwargs)
        if not (hasattr(func, "__editor_disable_update__") and func.__editor_disable_update__):
            await editor.update()
        if not (
            hasattr(func, "__editor_disable_message_update__")
                and func.__editor_disable_message_update__
        ):
            await editor.update_message()
        return response
    return wrapper


class EditorPage(ui.View):
    """
    This class represents a single menu for an editor.
    It inherits from `discord.ui.View`.
    An editor page also keeps reference to a message, which is where it appears as a View object.
    An embed may also be stored inside this object for further editing.

    Note: When overriding the __init__ magic method, the super call should be placed last!
    Do not mess with this unless you know what you are doing. An early __init__ call may result
    in broken callbacks and other anomalies!
    """
    timeout: float|None
    resets_message_content: bool

    def __init__(
        self,
        message: discord.Message|None=None,
        embed: discord.Embed|None=None
    ):
        self.message = message
        self.embed = embed
        super().__init__(timeout=type(self).timeout)
        # Inject post-interaction editor updates.
        for item in self.children:
            item.callback = _wraps_update(self, item.callback)
    
    def __init_subclass__(
        cls,
        *,
        timeout: float|None=180,
        resets_message_content: bool=False
    ) -> None:
        cls.timeout = timeout
        cls.resets_message_content = resets_message_content

        return super().__init_subclass__()
    
    async def update(self):
        """
        Responsible for updating this objects settings and embed content.
        By default, will be called after every finished message component interaction,
        but before `update_message`.

        Subclasses should override this method.
        """
    
    async def update_message(self):
        """
        This method updates the editor message and is called just after `update`.
        If the `reset_message_content` option was enabled on subclassing, it will also
        clear the message content.

        Overriding the class is legal, but overriding `update` instead should be considered.
        Note that certain decorators may result in this method being called more often than
        expected. There is no guarantee to the call-scheduling of this method.

        For components that are annotated via the `@disable_update` decorator, this method
        will still be called by default.
        """
        if self.message is None:
            LOGGER.warning("EditorPage.update_message called without set message!")
            return
        await self.message.edit(
            content=None if type(self).resets_message_content else MISSING,
            embed=self.embed,
            view=self
        )
    
    async def set_component_state(self, state: bool):
        """
        Sets all children of this view to have the passed disabled state.
        Note that `True` means all items will be disabled.

        Also calls `update_message`.
        """
        for item in self.children:
            item.disabled = state  # type: ignore
        await self.update_message()


class disable_when_processing(Generic[T, *Ts]):
    """
    Decorator to disable all components while a callback is executing.
    This may be used when longer operations are expected to combat race conditions.

    Internally this decorator calls `EditorPage.update_message` twice,
    once before and once after the callback.
    This should be considered when that method is overridden.
    """
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


def disable_update(
    func: GenericCoroutineFunction|None=None,
    *,
    disable_update: bool=True,
    disable_message_update: bool=False
) -> GenericCoroutineFunction|Callable[[GenericCoroutineFunction], GenericCoroutineFunction]:
    """
    Marks an item callback to not call the update methods after it finishes.
    Only disables `EditorPage.update` by default,
    but can be configured for `EditorPage.update_message` too.
    """
    def decorator(decorator_func: GenericCoroutineFunction) -> GenericCoroutineFunction:
        decorator_func.__editor_disable_update__ = disable_update
        decorator_func.__editor_disable_message_update__ = disable_message_update
        return decorator_func
    if func is None:
        return decorator
    else:
        return decorator(func)
