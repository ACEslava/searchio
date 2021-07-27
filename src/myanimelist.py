import asyncio
from typing import Optional

import discord
from discord.ext import commands
from discord.ext.commands import bot, context
from mal import AnimeSearch

from src.utils import Log, error_handler, Sudo

class MyAnimeListSearch:
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

        UserCancel = KeyboardInterrupt

        def search_pages(result_) -> discord.Embed:
            return discord.Embed(
                title=f"Titles matching '{self.query}'",
                description="\n".join(
                    [
                        f"[{index_}]: {value.title}"
                        for index_, value in enumerate(result_)
                    ]
                ),
            )

        try:
            errorMessage = None
            search = AnimeSearch(self.query)

            while 1:
                result = [
                    [anime for anime in search.results][x : x + 10]
                    for x in range(0, len([anime for anime in search.results]), 10)
                ]
                embeds = list(map(search_pages, result))
                cur_page = 0

                for index, item in enumerate(embeds):
                    item.set_footer(
                        text=f"Please choose option or cancel\nPage {index+1}/{len(embeds)}"
                    )

                await self.message.add_reaction("🗑️")
                if len(embeds) > 1:
                    await self.message.add_reaction("◀️")
                    await self.message.add_reaction("▶️")

                while 1:
                    try:
                        await self.message.edit(
                            content='', embed=embeds[cur_page % len(embeds)]
                        )
                        emojitask = asyncio.create_task(
                            self.bot.wait_for(
                                "reaction_add",
                                check=
                                    lambda reaction_, user_: Sudo.pageTurnCheck(
                                        reaction_, 
                                        user_, 
                                        self.message, 
                                        self.bot, 
                                        self.ctx),
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
                            await self.message.remove_reaction(reaction, user)

                            if str(reaction.emoji) == "🗑️":
                                await self.message.delete()
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

                                if errorMessage is not None:
                                    await errorMessage.delete()
                                    
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

                                Log.append_to_log(self.ctx, f"{self.ctx.command} result", anime_item.title)
                                await self.message.clear_reactions()
                                await self.message.edit(embed=embed)
                                await self.message.add_reaction("🗑️")
                                reaction, user = await self.bot.wait_for(
                                    "reaction_add",
                                    check=
                                        lambda reaction_, user_: Sudo.pageTurnCheck(
                                            reaction_, 
                                            user_, 
                                            self.message, 
                                            self.bot, 
                                            self.ctx),
                                    timeout=60,
                                )
                                if str(reaction.emoji) == "🗑️":
                                    await self.message.delete()
                                return

                            except (ValueError, IndexError):
                                errorMessage = await self.ctx.send(content="Invalid choice. Please choose a number between 0-9 or cancel")
                                continue

                            except asyncio.TimeoutError:
                                await self.message.clear_reactions()
                                return

                    except UserCancel:

                        await self.message.delete()

                    except asyncio.TimeoutError:
                        await self.message.delete()

                    except (asyncio.CancelledError, discord.errors.NotFound):
                        pass

                    except Exception:
                        await self.message.delete()
                        raise

        except Exception as e:
            await error_handler(self.bot, self.ctx, e, self.query)
        finally:
            return
