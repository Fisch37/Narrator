"""
Implements a Transformer to allow easy parsing of mask names into the masks.
"""
from itertools import islice
from typing import Sequence

import discord
from discord.app_commands import Transformer, Transform, Choice, TransformerError

from data.sql.ormclasses import Mask
from data.utils.masks import cached_mask_names_by_member


class MaskTransformer(Transformer):
    """
    This transformer allows mask names to be parsed into mask instances.
    It also includes an autocomplete functionality.
    """
    
    async def transform(self, interaction: discord.Interaction, name: str) -> Mask:
        mask = await Mask.get_by_name_and_owner_and_guild(name, interaction.user)
        if mask is None:
            raise TransformerError(name, self.type, self)
        return mask
    
    async def autocomplete(self, interaction: discord.Interaction, name: str) -> list[Choice]:
        if interaction.guild is None:
            return []
        mask_names: Sequence[str] = await cached_mask_names_by_member(interaction.user)
        filtered_masks = filter(lambda mask_name: mask_name.startswith(name), mask_names)
        return [
            Choice(
                name=name,
                value=name
            )
            for name in islice(filtered_masks, 25)
        ]


MaskParameter = Transform[Mask, MaskTransformer]
