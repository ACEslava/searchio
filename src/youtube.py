from datetime import datetime, timedelta

import asyncio
import discord
import os
import requests
import yaml
from discord.ext import commands
from pytube import YouTube as YoutubeDownload
from youtube_search import YoutubeSearch as YTSearch

from src.loadingmessage import get_loading_message
from src.utils import ErrorHandler


class YoutubeSearch:
    @staticmethod
    async def search(
        bot: commands.Bot,
        ctx: commands.Context,
        message: discord.Message,
        search_query: str,
        user_settings: dict,
    ) -> None:
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
            embed_.set_footer(text=f"Requested by {ctx.author}")
            return embed_

        try:
            result = YTSearch(search_query, max_results=10).to_dict()

            embeds = list(map(result_embed, result))

            do_exit, cur_page = False, 0
            await message.add_reaction("🗑️")
            await message.add_reaction("⬇️")
            if len(embeds) > 1:
                await message.add_reaction("◀️")
                await message.add_reaction("▶️")
            elif len(embeds) == 0:
                embed = discord.Embed(
                    description=f"No results found for: {search_query}"
                )
                await message.edit(content=None, embed=embed)
                await asyncio.sleep(60)
                await message.delete()
                return
            while not do_exit:
                try:
                    await message.edit(
                        content=None, embed=embeds[cur_page % len(embeds)]
                    )
                    reaction, user = await bot.wait_for(
                        "reaction_add",
                        check=lambda reaction_, user_: all(
                            [
                                str(reaction_.emoji) in ["◀️", "▶️", "🗑️", "⬇️"],
                                reaction_.message == message,
                                not user_.bot,
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
                    elif (
                        str(reaction.emoji) == "⬇️"
                        and user_settings[user.id]["downloadquota"]["dailyDownload"]
                        < 50
                    ):
                        await message.remove_reaction(reaction, bot.user)
                        downloadmessage = await ctx.send(
                            f"{get_loading_message()} <a:loading:829119343580545074>"
                        )
                        yt = YoutubeDownload(embeds[cur_page].url)
                        download = yt.streams.filter(
                            res="360p", file_extension="mp4", progressive=True
                        ).fmt_streams[0]
                        if round(download.filesize_approx / 1000000, 2) < 100:
                            embed = discord.Embed(
                                description=(
                                    f"{user}, "
                                    f"This download will use {round(download.filesize_approx/1000000, 2)}MB "
                                    f"of your remaining "
                                    f"{50 - user_settings[user.id]['downloadquota']['dailyDownload']}MB daily quota\n"
                                    "Do you want to continue?"
                                )
                            )
                            await downloadmessage.edit(content=None, embed=embed)
                            await downloadmessage.add_reaction("👍")
                            await downloadmessage.add_reaction("👎")
                            dlreaction, dluser = await bot.wait_for(
                                "reaction_add",
                                check=lambda dlreaction_, dluser_: all(
                                    [
                                        dluser_ == user,
                                        str(dlreaction_.emoji) in ["👍", "👎"],
                                        dlreaction_.message == downloadmessage,
                                    ]
                                ),
                                timeout=30,
                            )

                            if str(dlreaction.emoji) == "👍":
                                await downloadmessage.clear_reactions()
                                await downloadmessage.edit(
                                    content=f"{get_loading_message()} <a:loading:829119343580545074>",
                                    embed=None,
                                )

                                user_settings[user.id]["downloadquota"][
                                    "dailyDownload"
                                ] += round(download.filesize_approx / 1000000, 2)
                                user_settings[user.id]["downloadquota"][
                                    "lifetimeDownload"
                                ] += round(download.filesize_approx / 1000000, 2)
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
                                        f"{share_link}\n\nHere is your download link. "
                                        "You now have "
                                        f"{50 - user_settings[user.id]['downloadquota']['dailyDownload']}MB "
                                        f"left in your daily quota."
                                        "Negative values mean your daily quota for the next day will be subtracted."
                                    )
                                )
                                embed.set_footer(text=f"Requested by {user}")
                                await downloadmessage.delete()
                                await ctx.send(embed=embed)

                                with open("userSettings.yaml", "w") as data:
                                    yaml.dump(user_settings, data, allow_unicode=True)
                            elif str(dlreaction.emoji) == "👎":
                                await downloadmessage.delete()
                                await message.add_reaction("⬇️")

                        else:
                            embed = discord.Embed(
                                description=(
                                    f"{user}, "
                                    f"this download is {round(download.filesize_approx/1000000, 2)}MB, "
                                    f"which exceeds the maximum filesize of 100MB. It will not be processed."
                                )
                            )
                            await downloadmessage.edit(content=None, embed=embed)

                except asyncio.TimeoutError:
                    await message.clear_reactions()
                except asyncio.CancelledError:
                    pass

        except UserCancel:
            await ctx.send(f"Cancelled")

        except asyncio.TimeoutError:
            await ctx.send(f"Search timed out. Aborting")

        except Exception as e:
            await ErrorHandler(bot, ctx, e, search_query)
        finally:
            return


class UserCancel(Exception):
    pass
