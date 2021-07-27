import asyncio
import datetime
import difflib
import json
import random
import urllib.request as ureq

import discord
from discord import message
from discord.ext import commands
from discord.ext.commands import bot, context

from src.utils import Log, error_handler, Sudo
class XKCDSearch:
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
        error_count = 0

        while error_count <= 1:
            try:
                x = self.Xkcd(self.query)
                embed = discord.Embed(
                    title=x.title, description=x.alt, timestamp=x.date
                )
                embed.url = x.url
                embed.set_image(url=x.img_url)
                embed.set_footer(text=f"Requested by {self.ctx.author}")

                await self.message.edit(content='', embed=embed)
                Log.append_to_log(self.ctx, f"{self.ctx.command} result", x.url)

                await self.message.add_reaction("🗑️")
                reaction, _ = await self.bot.wait_for(
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

            except UserCancel:
                await self.ctx.send(f"Cancelled")
                return

            except ValueError:
                error_msg = await self.ctx.send(
                    "Invalid input, an XKCD comic number is needed. Please edit your search or try again."
                )

                self.message_edit = asyncio.create_task(
                    self.bot.wait_for(
                        "self.message_edit",
                        check=lambda var, m: m.author == self.ctx.author,
                        timeout=60,
                    )
                )
                reply = asyncio.create_task(
                    self.bot.wait_for(
                        "self.message", check=lambda m: m.author == self.ctx.author, timeout=60
                    )
                )

                waiting = [self.message_edit, reply]
                done, waiting = await asyncio.wait(
                    waiting, return_when=asyncio.FIRST_COMPLETED
                )  # 30 seconds wait either reply or react
                if self.message_edit in done:
                    reply.cancel()
                    self.message_edit = self.message_edit.result()
                    self.query = "".join(
                        [
                            li
                            for li in difflib.ndiff(
                                self.message_edit[0].content, self.message_edit[1].content
                            )
                            if "+" in li
                        ]
                    ).replace("+ ", "")
                elif reply in done:
                    self.message_edit.cancel()
                    reply = reply.result()
                    await reply.delete()

                    if reply.content == "cancel":
                        self.message_edit.cancel()
                        reply.cancel()
                        break
                    else:
                        self.query = reply.content
                await error_msg.delete()
                error_count += 1
                continue

            except asyncio.TimeoutError:
                return

            except (asyncio.CancelledError, discord.errors.NotFound):
                pass

            except Exception as e:
                await error_handler(self.bot, self.ctx, e, self.query)
                return

    class Xkcd:
        def __init__(self, num=""):
            if num.lower() == "random":
                self.num = random.randrange(1, self.Xkcd("").num)
            elif str(num).isnumeric() or num == "":
                self.num = num
            elif num.lower() == "latest":
                self.num = self.Xkcd("").num
            else:
                raise ValueError

            self.url = "https://xkcd.com/" + str(self.num)

            mdata = json.load(ureq.urlopen(self.url + "/info.0.json"))
            self.date = datetime.datetime(
                int(mdata["year"]), int(mdata["month"]), int(mdata["day"])
            )
            self.img_url = mdata["img"]
            self.title = mdata["title"]
            self.alt = mdata["alt"]
            self.num = mdata["num"]