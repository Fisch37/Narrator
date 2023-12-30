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

def get_all_subchannels(channel: HierarchyNode) -> Generator[HierarchySubnode, None, None]:
    """
    Recursively yields all direct and indirect subchannels of the passed channel.
    Direct subchannels are yielded with their children directly following.
    This is equivalent to the "visual" ordering of channels in the Discord UI.
    """
    subchannels = get_subchannels(channel)
    for sub in subchannels:
        yield sub
        yield from get_all_subchannels(sub)
