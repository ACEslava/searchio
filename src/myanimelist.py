import asyncio
from typing import Optional

import discord
from discord.ext import commands
from mal import *

from src.utils import Log, error_handler


class MyAnimeListSearch:
    def __init__(
        self,
        bot: commands.Bot,
        ctx: commands.Context,
        message: discord.Message,
        search_query: Optional[str] = None,
    ):

        self.search_query = search_query
        self.bot = bot
        self.ctx = ctx
        self.message = message

    async def search(self) -> None:
        def search_pages(result_) -> discord.Embed:
            return discord.Embed(
                title=f"Titles matching '{self.search_query}'",
                description="\n".join(
                    [
                        f"[{index_}]: {value.title}"
                        for index_, value in enumerate(result_)
                    ]
                ),
            )

        try:
            msg = [self.message]
            search = AnimeSearch(self.search_query)

            while 1:
                result = [
                    [anime for anime in search.results][x : x + 10]
                    for x in range(0, len([anime for anime in search.results]), 10)
                ]
                embeds = list(map(search_pages, result))
                cur_page = 0

                for index, item in enumerate(embeds):
                    item.set_footer(
                        text=f"Page {index+1}/{len(embeds)}\nRequested by: {str(self.ctx.author)}"
                    )

                await msg[0].add_reaction("🗑️")
                if len(embeds) > 1:
                    await msg[0].add_reaction("◀️")
                    await msg[0].add_reaction("▶️")
                msg.append(await self.ctx.send("Please choose option or cancel"))

                while 1:
                    try:
                        await msg[0].edit(
                            content=None, embed=embeds[cur_page % len(embeds)]
                        )
                        emojitask = asyncio.create_task(
                            self.bot.wait_for(
                                "reaction_add",
                                check=lambda reaction_, user_: all(
                                    [
                                        user_ == self.ctx.author,
                                        str(reaction_.emoji) in ["◀️", "▶️", "🗑️"],
                                        reaction_.message == msg[0],
                                    ]
                                ),
                                timeout=60,
                            )
                        )
                        responsetask = asyncio.create_task(
                            self.bot.wait_for(
                                "message",
                                check=lambda m: m.author == self.ctx.author,
                                timeout=30,
                            )
                        )

                        waiting = [emojitask, responsetask]
                        done, waiting = await asyncio.wait(
                            waiting, return_when=asyncio.FIRST_COMPLETED
                        )  # 30 seconds wait either reply or react
                        if emojitask in done:
                            reaction, user = emojitask.result()
                            await msg[0].remove_reaction(reaction, user)

                            if str(reaction.emoji) == "🗑️":
                                await msg[0].delete()
                                return
                            elif str(reaction.emoji) == "◀️":
                                cur_page -= 1
                            elif str(reaction.emoji) == "▶️":
                                cur_page += 1

                        elif responsetask in done:
                            try:
                                emojitask.cancel()
                                input = responsetask.result()
                                await input.delete()
                                if input.content.lower() == "cancel":
                                    raise UserCancel
                                input = int(input.content)
                                anime_item = result[cur_page][input]

                                embed = discord.Embed(
                                    title=f"{anime_item.title}",
                                    description=anime_item.synopsis,
                                    url=anime_item.url,
                                )  # Myanimelist data

                                embed.add_field(
                                    name="MyAnimeListID",
                                    value=str(anime_item.mal_id),
                                    inline=True,
                                )
                                embed.add_field(
                                    name="Rating",
                                    value=str(anime_item.score),
                                    inline=True,
                                )
                                embed.add_field(
                                    name="Episodes",
                                    value=str(anime_item.episodes),
                                    inline=True,
                                )

                                embed.set_thumbnail(url=anime_item.image_url)
                                embed.set_footer(text=f"Requested by {self.ctx.author}")
                                searchresult = await self.ctx.send(embed=embed)

                                Log.append_to_log(self.ctx, f"{self.ctx.command} result", anime_item.title)
                                for message in msg:
                                    await message.delete()

                                await searchresult.add_reaction("🗑️")
                                reaction, user = await self.bot.wait_for(
                                    "reaction_add",
                                    check=lambda reaction_, user_: all(
                                        [
                                            user_ == self.ctx.author,
                                            str(reaction_.emoji) == "🗑️",
                                        ]
                                    ),
                                    timeout=60,
                                )
                                if str(reaction.emoji) == "🗑️":
                                    await searchresult.delete()
                                return

                            except ValueError or IndexError:
                                await msg[-1].edit(
                                    content="Invalid choice. Please choose a number between 0-9 or cancel"
                                )
                                continue

                            except asyncio.TimeoutError:
                                await searchresult.clear_reactions()
                                return

                            except asyncio.CancelledError:
                                pass

                    except UserCancel:

                        for message in msg:
                            await message.delete()

                    except asyncio.TimeoutError:
                        for message in msg:
                            await message.delete()

                    except asyncio.CancelledError:
                        await self.ctx.send(f"Search timed out. Aborting")

                    except Exception:
                        for message in msg:
                            await message.delete()
        except Exception as e:
            await error_handler(self.bot, self.ctx, e, self.search_query)
        finally:
            return


class UserCancel(Exception):
    pass
