"""
This util aims to provide logic that helps in evaluating channel hierarchies in Discord.

The logic is as follows:
    Guild
        |
        ∟ CategoryChannel
            ⊢ TextChannel
            |   ∟ Thread
            ⊢ ForumChannel
            |   ∟ Thread
            ⊢ VoiceChannel
            ∟ Stage Channel

Note that at any point there can be multiple entries and the figure above is unordered.
For the purposes of this module, the term "channel" also includes Threads and Guilds.

Some functions in here may be async others may not.

Private channels do not have a hierarchy and are thus not supported.
"""
from typing import Generator, Literal, Sequence, overload, Union, Never
from itertools import filterfalse
import discord

HierarchyRoot = discord.Guild
HierarchyBranch = discord.abc.GuildChannel
HierarchyLeaf = discord.Thread
HierarchyParent = HierarchyRoot|HierarchyBranch
HierarchySubnode = HierarchyBranch|HierarchyLeaf
HierarchyNode = HierarchyRoot|HierarchySubnode
CategorySubchannels = Union[
    discord.TextChannel,
    discord.VoiceChannel,
    discord.StageChannel,
    discord.ForumChannel
]

_SUBCHANNEL_LUT: dict[type[HierarchyNode], str|None] = {
    discord.Guild : "channels", # This includes categories as well
    discord.CategoryChannel : "channels",
    discord.TextChannel : "threads",
    discord.ForumChannel : "threads",
    discord.VoiceChannel : None,
    discord.StageChannel : None,
    discord.Thread : None,
}
_PARENT_LUT: dict[type[HierarchyNode], tuple[str, ...]|None] = {
    discord.Guild : None,
    discord.CategoryChannel : ("guild",),
    discord.TextChannel : ("category", "guild"),
    discord.ForumChannel : ("category", "guild"),
    discord.VoiceChannel : ("category", "guild"),
    discord.StageChannel : ("category", "guild"),
    discord.Thread : ("parent",),
}

@overload
def get_subchannels(channel: discord.Guild) -> list[discord.abc.GuildChannel]: ...

@overload
def get_subchannels(channel: discord.CategoryChannel) -> list[CategorySubchannels]: ...

@overload
def get_subchannels(channel: discord.TextChannel|discord.ForumChannel) -> list[discord.Thread]: ...

@overload
def get_subchannels(
    channel: discord.VoiceChannel|discord.StageChannel|discord.Thread
) -> list[Never]: ...

@overload
def get_subchannels(channel: HierarchyNode) -> Sequence[HierarchySubnode]: ...

def get_subchannels(channel: HierarchyNode) -> Sequence[HierarchySubnode]:
    """
    This function returns all the direct subchannels of the passed channel.
    
    Raises `TypeError` when the entered channel is not supported.
    
    Note that this function requires the values to be cached, which may not be the case.
    If you need certainty, use fetch_subchannels or may_fetch_subchannels instead.
    """
    try:
        attribute = _SUBCHANNEL_LUT[type(channel)]
    except KeyError as e:
        raise TypeError(
            "The channel you passed is not of a known channel type.\
            This may be due to invalid input or an unsupported version of discord.py"
        ) from e
    else:
        if attribute is None:
            return []
        return getattr(channel, attribute)

def get_all_subchannels(
    channel: HierarchyNode,
    *,
    breadth_first: bool=False
) -> Generator[HierarchySubnode, None, None]:
    """
    Recursively yields all direct and indirect subchannels of the passed channel.
    By default, subchannels are yielded depth-first, which is 
    equivalent to the "visual" ordering of channels in the Discord UI.
    
    The `breadth_first` flag may be used to enable breadth-first traversal.
    This mode may prove faster when in case of a recursive search, 
    but is less intuitive in its sequencing.
    """
    # Doing these as seperate functions to avoid checking for the flag on every layer.
    if not breadth_first:
        return _get_all_subchannels_depth(channel)
    return _get_all_subchannels_breadth(channel)

def is_subchannel(channel: HierarchySubnode, parent: HierarchyNode) -> bool:
    """
    Returns whether the passed channel is a subchannel of parent.
    
    This differs from `channel in get_subchannels(parent)` 
    because it searches the entire subtree (meaning it includes sub-subchannels)
    """
    # Breadth-first allows for usually quicker searches as (for example)
    # users find themselves inside of threads significantly less often.
    return channel in get_all_subchannels(parent, breadth_first=True)


def _get_all_subchannels_depth(channel: HierarchyNode) -> Generator[HierarchySubnode, None, None]:
    subchannels = get_subchannels(channel)
    for sub in subchannels:
        yield sub
        yield from _get_all_subchannels_depth(sub)

def _get_all_subchannels_breadth(channel: HierarchyNode) -> Generator[HierarchySubnode, None, None]:
    subchannels = get_subchannels(channel)
    yield from subchannels
    for sub in subchannels:
        yield from _get_all_subchannels_breadth(sub)


@overload
def get_parent(channel: discord.Guild) -> None: ...

@overload
def get_parent(channel: discord.CategoryChannel) -> discord.Guild: ...

@overload
def get_parent(channel: Union[
    discord.TextChannel,
    discord.ForumChannel,
    discord.VoiceChannel,
    discord.StageChannel
    ]) -> discord.Guild|discord.CategoryChannel: ...

@overload
def get_parent(channel: discord.Thread) -> discord.TextChannel|discord.ForumChannel: ...

@overload
def get_parent(channel: HierarchyNode) -> HierarchyParent|None: ...

def get_parent(channel: HierarchyNode) -> HierarchyParent|None:
    try:
        attributes = _PARENT_LUT[type(channel)]
    except KeyError as e:
        raise TypeError(
            f"Object of type {type(channel)} is not a supported channel type.\
            This may be caused by an invalid variable type or an unsupported version of discord.py"
        )
    else:
        if attributes is None:
            return None
        # Return first non-None attribute
        # (there have to be multiple attributes because 
        # GuildChannels may or may not be in a category)
        return next(filterfalse(
            lambda result: result is None,
            (
                getattr(channel, attr) 
                for attr in attributes
            )
        ))

def is_parent(parent: HierarchyNode, child: HierarchyNode) -> bool:
    """
    Checks whether a channel is a parent of another channel.
    
    This differs from a simple `parent == get_parent(child)` call
    since it recursively checks the entire tree upward.
    """
    actual_parent = get_parent(child)
    if actual_parent is None:
        return False
    if parent == actual_parent:
        return True
    return is_parent(parent, actual_parent)

## These are, by far, not all overloads that should be here, but doing all those permutations
## will make my head explode so I'll just add stuff when I find out it's missing.
@overload
def get_all_parents(
    channel: HierarchyRoot,
    *,
    include_this: Literal[True],
    include_root: bool=True
) -> Generator[HierarchyRoot, None, None]: ...

@overload
def get_all_parents(
    channel: HierarchyRoot,
    *,
    include_this: Literal[False],
    include_root: bool=True
) -> Generator[Never, None, None]: ...

@overload
def get_all_parents(
    channel: HierarchySubnode,
    *,
    include_this: Literal[False],
    include_root: Literal[False]
) -> Generator[HierarchyBranch, None, None]: ...

@overload
def get_all_parents(
    channel: HierarchySubnode,
    *,
    include_this: Literal[True],
    include_root: Literal[False]
) -> Generator[HierarchySubnode, None, None]: ...

@overload
def get_all_parents(
    channel: HierarchySubnode,
    *,
    include_this: Literal[False],
    include_root: bool=True
) -> Generator[HierarchyParent, None, None]: ...

@overload  # Catch-all overload
def get_all_parents(
    channel: HierarchyNode,
    *,
    include_this: bool=False,
    include_root: bool=True
) -> Generator[HierarchyNode, None, None]: ...

def get_all_parents(
    channel: HierarchyNode,
    *,
    include_this: bool=False,
    include_root: bool=True
) -> Generator[HierarchyNode, None, None]:
    """
    Yields all parents of the passed channel from lowest to highest.
    
    If `include_this` is set to True, the first element will be the passed channel.
    
    If `include_root` is set to True (the default), 
    the last element will always be a `HierarchyRoot` object.
    """
    if include_this:
        yield channel
    parent = get_parent(channel)
    if parent is None:
        return
    
    if include_root or not isinstance(parent, HierarchyRoot):
        yield parent
    yield from get_all_parents(parent, include_this=False, include_root=include_root)
