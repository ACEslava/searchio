import asyncio
import datetime
import difflib
import json
import random
import urllib.request as ureq

import discord
from discord.ext import commands

from src.utils import Log, ErrorHandler


class Xkcd:
    def __init__(self, num=""):
        if num.lower() == "random":
            self.num = random.randrange(1, Xkcd("").num)
        elif str(num).isnumeric() or num == "":
            self.num = num
        elif num.lower() == "latest":
            self.num = Xkcd("").num
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


class XKCDSearch:
    @staticmethod
    async def search(
        bot: commands.Bot,
        ctx: commands.Context,
        search_query: str,
        message: discord.Message,
    ):
        error_count = 0
        while error_count <= 1:
            try:
                x = Xkcd(search_query)
                embed = discord.Embed(
                    title=x.title, description=x.alt, timestamp=x.date
                )
                embed.url = x.url
                embed.set_image(url=x.img_url)
                embed.set_footer(text=f"Requested by {ctx.author}")

                await message.edit(content=None, embed=embed)
                Log.appendToLog(ctx, f"{ctx.command} result", x.url)

                await message.add_reaction("🗑️")
                reaction, user = await bot.wait_for(
                    "reaction_add",
                    check=lambda reaction_, user_: all(
                        [
                            user_ == ctx.author,
                            str(reaction_.emoji) == "🗑️",
                            reaction_.message == message,
                        ]
                    ),
                    timeout=60,
                )
                if str(reaction.emoji) == "🗑️":
                    await message.delete()
                return

            except UserCancel:
                await ctx.send(f"Cancelled")
                return

            except ValueError:
                error_msg = await ctx.send(
                    "Invalid input, an XKCD comic number is needed. Please edit your search or try again."
                )

                message_edit = asyncio.create_task(
                    bot.wait_for(
                        "message_edit",
                        check=lambda var, m: m.author == ctx.author,
                        timeout=60,
                    )
                )
                reply = asyncio.create_task(
                    bot.wait_for(
                        "message", check=lambda m: m.author == ctx.author, timeout=60
                    )
                )

                waiting = [message_edit, reply]
                done, waiting = await asyncio.wait(
                    waiting, return_when=asyncio.FIRST_COMPLETED
                )  # 30 seconds wait either reply or react
                if message_edit in done:
                    reply.cancel()
                    message_edit = message_edit.result()
                    search_query = "".join(
                        [
                            li
                            for li in difflib.ndiff(
                                message_edit[0].content, message_edit[1].content
                            )
                            if "+" in li
                        ]
                    ).replace("+ ", "")
                elif reply in done:
                    message_edit.cancel()
                    reply = reply.result()
                    await reply.delete()

                    if reply.content == "cancel":
                        message_edit.cancel()
                        reply.cancel()
                        break
                    else:
                        search_query = reply.content
                await error_msg.delete()
                error_count += 1
                continue

            except asyncio.TimeoutError:
                return

            except asyncio.CancelledError:
                pass

            except Exception as e:
                await ErrorHandler(bot, ctx, e, search_query)
                return


class UserCancel(Exception):
    pass
