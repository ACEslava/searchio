import asyncio
from typing import Optional

import discord
import wikipedia as Wikipedia
from discord.ext import commands

from src.loadingmessage import get_loading_message
from src.utils import error_handler, Sudo


class WikipediaSearch:
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

        if self.args is None:
            Wikipedia.set_lang("en")
        elif any("lang" in i for i in self.args):
            language = self.args[
                [idx for idx, s in enumerate(self.args) if "lang" in s][0]
            ].replace("lang ", "")
            Wikipedia.set_lang(language)

        def search_pages(result_) -> discord.Embed:
            return discord.Embed(
                title=f"Titles matching '{self.query}'",
                description="\n".join(
                    [f"[{index_}]: {value}" for index_, value in enumerate(result_)]
                ),
            )

        try:
            errorMessage = None
            result = Wikipedia.search(self.query)

            while 1:
                result = [result[x : x + 10] for x in range(0, len(result), 10)]
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
                                try:
                                    emojitask.cancel()
                                    input = responsetask.result()
                                    await input.delete()
                                    if input.content.lower() == "cancel":
                                        raise UserCancel

                                    input = int(input.content)
                                    
                                    if errorMessage is not None:
                                        await errorMessage.delete()

                                    self.query = result[cur_page][input]
                                    page = Wikipedia.WikipediaPage(
                                        title=self.query
                                    )
                                    summary = page.summary[
                                        : page.summary.find(". ") + 1
                                    ]
                                    embed = discord.Embed(
                                        title=f"Wikipedia Article: {page.original_title}",
                                        description=summary,
                                        url=page.url,
                                    )  # outputs wikipedia article
                                    embed.set_footer(
                                        text=f"Requested by {self.ctx.author}"
                                    )

                                    await self.message.edit(embed=embed)
                                    await self.message.clear_reactions()
                                    await self.message.add_reaction("🗑️")
                                    await self.bot.wait_for(
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
                                    return

                                except Wikipedia.DisambiguationError as e:
                                    result = str(e).split("\n")
                                    result.pop(0)
                                    await self.message.edit(content=f"{get_loading_message()}")
                                    break
                                
                                except (ValueError, IndexError):
                                    errorMessage = await self.ctx.send(
                                        "Invalid choice. Please choose a number between 0-9 or cancel"
                                    )
                                continue

                            except asyncio.TimeoutError:
                                await self.message.clear_reactions()
                                return

                    except (UserCancel, asyncio.TimeoutError):
                        await self.message.delete()

                    except (asyncio.CancelledError, discord.errors.NotFound):
                        pass

                    except Exception:
                        raise

        except Exception as e:
            await error_handler(self.bot, self.ctx, e, self.query)
        finally:
            return
