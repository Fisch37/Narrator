"""
This module provides an pool object that manages webhooks for the bot.
There should only be one of these pools per bot.
"""
from typing import Union

import discord
from discord import Webhook, WebhookType, Guild
from discord.ext.commands import Bot

SupportsWebhooks = Union[
    discord.TextChannel,
    discord.ForumChannel,
    discord.VoiceChannel,
    discord.StageChannel
]


class WebhookPool:
    """
    Pool for webhook objects.
    Caches found Webhook objects so as to reduce API traffic.
    There is currently no bound on the cache size.
    NOTE: When scaling up a cache bound might become necessary.
    """
    def __init__(self, bot: Bot):
        self.pool: dict[Guild, dict[SupportsWebhooks, Webhook]] = {}
        self._bot = bot

    async def get(
            self,
            channel: SupportsWebhooks,
            *,
            reason: str="New Webhook gathered from pool"
    ) -> Webhook:
        """
        Gets a bot-owned webhook for the specified channel.
        May use a cached webhook or create a new one if no usable
        webhook exists.
        NOTE: The caching implements no safeguard for deleting webhooks
        when in cache. This might induce race conditions.
        """
        guild = channel.guild
        self.pool.setdefault(guild, {})
        guild_pool = self.pool[guild]

        if channel.id not in guild_pool.keys():
            webhook = await self._fetch_webhook(channel) \
                or await self._create_new_webhook(channel, reason)
            guild_pool[channel] = webhook

        return guild_pool[channel]

    async def _fetch_webhook(
            self,
            channel: SupportsWebhooks
    ) -> Webhook|None:
        """
        Fetches and returns a webhook owned by the bot
        from the Discord API.
        Returns None if not existing.
        """
        try:
            return next(
                webhook
                for webhook in await channel.webhooks()
                if webhook.type == WebhookType.incoming
                and webhook.user == self._bot.user
            )
        except StopIteration:
            return None

    async def _create_new_webhook(
            self,
            channel: SupportsWebhooks,
            reason: str,
            /
    ) -> Webhook:
        return await channel.create_webhook(
            name=self._bot.user.name,
            avatar=await self._bot.user.avatar.read(),
            reason=reason
        )

    def clear(self):
        """
        Clears the pool cache.
        This does not delete any webhooks!
        """
        self.pool.clear()
