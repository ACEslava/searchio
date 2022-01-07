from datetime import datetime, timedelta
from pytube import YouTube as YoutubeDownload
from youtube_search import YoutubeSearch as YTSearch
import asyncio
import os
import requests
import yaml

import discord
from discord import message
from discord.ext.commands import bot
from discord.ext import commands
from discord_components import Button, ButtonStyle

from src.loadingmessage import get_loading_message
from src.utils import error_handler, Sudo


class YoutubeSearch:
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
        
        def result_embed(result_) -> discord.Embed:
            embed_ = discord.Embed(
                title=result_["title"],
                description=result_["long_desc"]
                if "long_desc" in result_.keys()
                else "No Description",
                url=f"https://www.youtube.com{result_['url_suffix']}",
            )
            embed_.add_field(name="Channel", value=result_["channel"], inline=True)
            embed_.add_field(name="Duration", value=result_["duration"], inline=True)
            embed_.add_field(name="Views", value=result_["views"], inline=True)
            embed_.add_field(
                name="Publish Time", value=result_["publish_time"], inline=True
            )

            embed_.set_thumbnail(url=result_["thumbnails"][0])
            embed_.set_footer(text=f"Requested by {self.ctx.author}")
            return embed_
      
        def download_embed(result_) -> discord.Embed:
            return discord.Embed(
                title=f"Available Videos",
                description="\n".join(
                    [f"[{index_}]: {value.resolution}, {round(value.filesize_approx/1000000, 2)}MB" for index_, value in enumerate(result_)]
                ),
            )

        try:
            result = YTSearch(
                self.query, 
                max_results=10
            ).to_dict()

            embeds = list(map(result_embed, result))
            if len(embeds) == 0:
                embed = discord.Embed(
                    description=f"No results found for: {self.query}"
                )
                await self.message.edit(content='', embed=embed)
                await asyncio.sleep(60)
                return
            elif len(embeds) == 1:
                emojis = ["🗑️", "⬇️"]
            else:
                emojis = ["🗑️","◀️","▶️", "⬇️"]
            
            cur_page = 0
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
                    resp = await self.bot.wait_for(
                        "button_click",
                        check=lambda b_ctx: b_ctx.message.id == self.message.id,
                        timeout=60
                    )

                    if str(resp.custom_id) == "🗑️":
                        await self.message.delete()
                        return
                    elif str(resp.custom_id) == "◀️":
                        cur_page -= 1
                    elif str(resp.custom_id) == "▶️":
                        cur_page += 1
                    elif str(resp.custom_id) in emojis:
                        await resp.respond(
                            type=7,
                            content='',
                            embed=embeds[cur_page % len(embeds)],
                            components=[[
                                Button(style=ButtonStyle.blue, label=e, custom_id=e)
                                for e in emojis
                                if e != '⬇️'
                            ]]
                        )

                        msg = [await self.ctx.send(
                            f"{get_loading_message()}"
                        )]
                        yt = YoutubeDownload(embeds[cur_page % len(embeds)].url)

                        download = yt.streams.filter(file_extension='mp4', progressive=True).order_by('resolution').fmt_streams
                        download = [vid for vid in download if round(vid.filesize_approx / 1000000, 2) < 100]
                        if len(download) != 0:
                            while 1:
                                download = [download[x : x + 10] for x in range(0, len(download), 10)] 
                                embeds = list(map(download_embed, download))
                                cur_page = 0

                                for index, item in enumerate(embeds):
                                    item.set_footer(
                                        text=f"Please choose option or cancel\nPage {index+1}/{len(embeds)}"
                                    )

                                if len(embeds) > 1:
                                    emojis = ["🗑️","◀️","▶️"]
                                else:
                                    emojis = ["🗑️"]

                                await msg[0].edit(
                                    content='', 
                                    embed=embeds[cur_page % len(embeds)],
                                    components=[[
                                        Button(style=ButtonStyle.blue, label=e, custom_id=e)
                                        for e in emojis
                                    ]]
                                )

                                while 1:
                                    emojitask = asyncio.create_task(
                                        self.bot.wait_for(
                                            "button_click",
                                            check=
                                                lambda b_ctx: Sudo.pageTurnCheck(
                                                    bot=self.bot,
                                                    ctx=resp,
                                                    button_ctx=b_ctx,
                                                    message=msg[0]
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

                                        except (ValueError, IndexError):
                                            await msg[-1].edit(
                                                content="Invalid choice. Please choose a number between 0-9 or cancel"
                                            )
                                            continue

                                        for self.message in msg: await self.message.delete()
                                        msg = [await self.ctx.send(f"{get_loading_message()}")]
                                        download = download[cur_page][input]

                                        self.userSettings[resp.author.id]["downloadquota"]["dailyDownload"] += round(download.filesize_approx / 1000000, 2)
                                        self.userSettings[resp.author.id]["downloadquota"]["lifetimeDownload"] += round(download.filesize_approx / 1000000, 2)
                                        download.download(output_path="./src/cache")

                                        best_server = requests.get(
                                            url="https://api.gofile.io/getServer"
                                        ).json()["data"]["server"]

                                        with open(
                                            f'{os.path.abspath(f"./src/cache/{download.default_filename}")}',
                                            "rb",
                                        ) as f:
                                            url = f"https://{best_server}.gofile.io/uploadFile"
                                            params = {
                                                "expire": round(
                                                    datetime.timestamp(
                                                        datetime.now() + timedelta(minutes=10)
                                                    )
                                                )
                                            }
                                            share_link = requests.post(
                                                url=url,
                                                params=params,
                                                files={
                                                    f'@{os.path.abspath(f"./src/cache/{download.default_filename}")}': f
                                                },
                                            ).json()["data"]["downloadPage"]

                                        os.remove(f"./src/cache/{download.default_filename}")
                                        embed = discord.Embed(
                                            description=(
                                                f"{share_link}\n\n"
                                                "You now have "
                                                f"{50 - round(self.userSettings[resp.author.id]['downloadquota']['dailyDownload'], 3)}MB "
                                                f"left in your daily quota. "
                                                "Negative values mean your daily quota for the next day will be subtracted."
                                            )
                                        )
                                        embed.set_footer(text=f"Requested by {resp.author}")
                                        for self.message in msg: await self.message.delete()
                                        await self.ctx.send(embed=embed)

                                        with open("userSettings.yaml", "w") as data:
                                            yaml.dump(self.userSettings, data, allow_unicode=True)
                        return

                    await resp.respond(
                        type=7,
                        content='',
                        embed=embeds[cur_page % len(embeds)]
                    )

                except TimeoutError:
                    await self.message.edit(
                        components=[]
                    )
                    return

        except UserCancel:
            await self.ctx.send(f"Cancelled")

        except asyncio.TimeoutError:
            await self.ctx.send(f"Search timed out. Aborting")

        except Exception as e:
            await error_handler(self.bot, self.ctx, e, self.query)
        finally:
            return
      