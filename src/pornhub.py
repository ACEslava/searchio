import asyncio

import discord
from discord import Embed
from discord.ext import commands
from pornhub_api import PornhubApi

from src.utils import ErrorHandler


class PornhubSearch:
    @staticmethod
    async def search(bot: commands.Bot, ctx: commands.Context, search_query: str, message: discord.Message):
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
            data = PornhubApi().search.search(search_query).videos[0:10]
            embeds = list(map(video_embed, data))

            for index, item in enumerate(embeds):
                item.set_footer(
                    text=f"Page {index+1}/{len(embeds)}\nRequested by: {str(ctx.author)}"
                )

            do_exit, cur_page = False, 0
            await message.add_reaction("🗑️")
            if len(embeds) > 1:
                await message.add_reaction("◀️")
                await message.add_reaction("▶️")

            while not do_exit:
                try:
                    await message.edit(
                        content=None, embed=embeds[cur_page % len(embeds)]
                    )
                    reaction, user = await bot.wait_for(
                        "reaction_add",
                        check=lambda reaction_, user_: all(
                            [
                                user_ == ctx.author,
                                str(reaction_.emoji) in ["◀️", "▶️", "🗑️"],
                                reaction_.message == message,
                            ]
                        ),
                        timeout=60,
                    )
                    await message.remove_reaction(reaction, user)

                    if str(reaction.emoji) == "🗑️":
                        await message.delete()
                        do_exit = True
                    elif str(reaction.emoji) == "◀️":
                        cur_page -= 1
                    elif str(reaction.emoji) == "▶️":
                        cur_page += 1

                except asyncio.TimeoutError:
                    raise
                except asyncio.CancelledError:
                    pass

        except asyncio.TimeoutError:
            raise
        except asyncio.CancelledError:
            pass

        except Exception as e:
            await message.delete()
            await ErrorHandler(bot, ctx, e, search_query)
        finally:
            return
