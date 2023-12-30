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
from typing import Any, Generator, Sequence, overload, Union, Never
import discord

HierarchyRoot = discord.Guild
HierarchyBranch = discord.abc.GuildChannel
HierarchyLeaf = discord.Thread
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
        if attribute is None:
            return []
        return getattr(channel, attribute)
    except KeyError as e:
        raise TypeError(
            "The channel you passed is not of a known channel type.\
            This may be due to invalid input or an unsupported version of discord.py"
        ) from e

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
        yield from _get_all_subchannels_breadth(channel)
