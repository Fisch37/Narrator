"""
This module provides a Modal subclass that automatically closes on a commit.

I don't know why this isn't the default behaviour or 
why this is so unneccesarily complicated to implement.
"""

import asyncio

from discord import Interaction
from discord.ui import Modal


class AutoStopModal(Modal):
    async def on_submit(self, interaction: Interaction):
        # Yes, I call this complicated. It should just be a class parameter.
        asyncio.create_task(interaction.response.defer())
        self.stop()
