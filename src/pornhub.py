import asyncio

import discord
from discord import Embed
from discord_components import Button, ButtonStyle
from discord.ext import commands
from pornhub_api import PornhubApi

from src.utils import error_handler, Sudo


class PornhubSearch:
    def __init__(
        self,
        bot: commands.Bot,
        ctx: commands.Context,
        server_settings: dict,
        user_settings: dict,
        message: discord.Message,
        args: list,
        query: str
    ):
        self.bot = bot
        self.ctx = ctx
        self.serverSettings = server_settings
        self.userSettings = user_settings
        self.message = message
        self.args = args
        self.query = query
        return

    async def __call__(self):
        def video_embed(video) -> Embed:
            embed = Embed(title=video.title)
            embed.add_field(name="Video ID", value=video.video_id)
            embed.add_field(name="Views", value=video.views)
            embed.add_field(name="Rating", value=video.rating)
            embed.add_field(
                name="Pornstars",
                value=", ".join(
                    [pornstar.pornstar_name for pornstar in video.pornstars]
                )
                if video.pornstars != []
                else "None listed",
            )
            embed.add_field(
                name="Publish Date", value=video.publish_date.strftime("%m/%d/%Y")
            )
            embed.add_field(name="Duration", value=video.duration)
            embed.add_field(
                name="Tags",
                value=", ".join(
                    [tag.tag_name for tag in video.tags]
                    if video.tags != []
                    else "None listed"
                ),
                inline=False,
            )

            embed.set_thumbnail(
                url=f"{video.default_thumb.scheme}://{video.default_thumb.host}/{video.default_thumb.path}"
            )
            embed.url = f"{video.url.scheme}://{video.url.host}{video.url.path}?viewkey={video.video_id}"
            return embed

        try:
            data = PornhubApi().search.search(self.query).videos[0:10]
            embeds = list(map(video_embed, data))

            for index, item in enumerate(embeds):
                item.set_footer(
                    text=f"Page {index+1}/{len(embeds)}\nRequested by: {str(self.ctx.author)}"
                )

            # sets the reactions for the search result
            if len(embeds) > 1:
                buttons = [[
                    {Button(style=ButtonStyle.grey, label="◀️", custom_id="◀️"): None},
                    {Button(style=ButtonStyle.red, label="🗑️", custom_id="🗑️"): None},
                    {Button(style=ButtonStyle.grey, label="▶️", custom_id="▶️"): None}
                ]]
            else:
                buttons = [[
                    Button(style=ButtonStyle.red, label="🗑️", custom_id="🗑️")
                ]]

            await Sudo.multi_page_system(self.bot, self.ctx, self.message, tuple(embeds), buttons)
            return

        except asyncio.TimeoutError:
            raise
        except (asyncio.CancelledError, discord.errors.NotFound):
            pass

        except Exception as e:
            await self.message.delete()
            await error_handler(self.bot, self.ctx, e, self.query)
        finally:
            await self.message.clear_reactions()
            return
