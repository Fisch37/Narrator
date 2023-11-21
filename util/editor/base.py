from typing import Any, Callable, Coroutine, TypeVar
from discord import Interaction, ui
from discord.ui.item import ItemCallbackType
import functools
import discord

MAXIMUM_ROW_CONTENT = 5
MAXIMUM_ROW_WITH_SELECT = 1
MAXIMUM_ROW_COUNT = 5

V = TypeVar('V', bound=ui.View)
ButtonCallbackType = ItemCallbackType[V, ui.Button[V]]


@functools.wraps(ui.button)
def button(*args, **kwargs):
    discord_decorator = ui.button(*args, **kwargs)
    
    def decorator(func: ButtonCallbackType) -> ButtonCallbackType:
        # discord.py _says_ they return a ui.Button object with this decorator.
        # They don't. They just annotate the function with magic attributes
        # and overwrite the definition in their __init_subclass__.
        # This is probably done to appease type checkers but it also sucks
        # because it leaves me having to find these things out by reading the source.
        # (also it misleads people about the true nature of the code)
        # What do I think they should've done? Really just do what they say they do
        # and override using a custom class. Much easier to build upon as well.
        # With this solution I need to emulate what they do so I don't break things.
        decorated_func: ButtonCallbackType = discord_decorator(func)  # type: ignore
        decorated_func.__is_editor_function__ = True
        return decorated_func
    return decorator


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
