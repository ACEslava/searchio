import asyncio
from typing import Optional

import discord
from discord.ext import commands
from discord_components import Button, ButtonStyle

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

                if len(embeds) > 1:
                    emojis = ["🗑️","◀️","▶️"]
                else:
                    emojis = ["🗑️"]

                await self.message.edit(
                    content='', 
                    embed=embeds[cur_page % len(embeds)],
                    components=[[
                        Button(style=ButtonStyle.blue, label=e, custom_id=e)
                        for e in emojis
                    ]]
                )

                while 1:
                    try:
                        emojitask = asyncio.create_task(
                            self.bot.wait_for(
                                "button_click",
                                check=
                                    lambda b_ctx: Sudo.pageTurnCheck(
                                        bot=self.bot,
                                        ctx=self.ctx,
                                        button_ctx=b_ctx,
                                        message=self.message
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
                            emojitask = emojitask.result()

                            if str(emojitask.custom_id) == "🗑️":
                                await self.message.delete()
                                return
                            elif str(emojitask.custom_id) == "◀️":
                                cur_page -= 1
                            elif str(emojitask.custom_id) == "▶️":
                                cur_page += 1

                            await emojitask.respond(
                                type=7,
                                content='',
                                embed=embeds[cur_page % len(embeds)]
                            )
                        
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
                                await self.message.edit(
                                    embed=embed,
                                    components=[
                                        Button(style=ButtonStyle.blue, label="🗑️", custom_id="🗑️")
                                    ]
                                )
                                await self.bot.wait_for(
                                    "button_click",
                                    check=
                                        lambda button_ctx: Sudo.pageTurnCheck(
                                            bot=self.bot,
                                            ctx=self.ctx,
                                            button_ctx=button_ctx,
                                            message=self.message
                                        ),
                                    timeout=60,
                                )
                                return

                            except (ValueError, IndexError):
                                errorMessage = await self.ctx.send(content="Invalid choice. Please choose a number between 0-9 or cancel")
                                continue

                            except asyncio.TimeoutError:
                                await self.message.edit(
                                    components=[]
                                )
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
