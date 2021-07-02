from youtube_search import YoutubeSearch as ytsearch
from datetime import datetime, timedelta
from src.utils import Log, ErrorHandler
from src.loadingmessage import LoadingMessage
from pytube import YouTube as YoutubeDownload
import discord, asyncio, random, os, yaml, requests

class YoutubeSearch:   
    @staticmethod
    async def search(bot, ctx, message, searchQuery, userSettings): 
        def resultEmbed(result):
            embed=discord.Embed(title=result['title'], 
                description=result['long_desc'] if 'long_desc' in result.keys() else 'No Description', 
                url=f"https://www.youtube.com{result['url_suffix']}")                  
            embed.add_field(name="Channel", value=result['channel'], inline=True)
            embed.add_field(name="Duration", value=result['duration'], inline=True)
            embed.add_field(name="Views", value=result['views'], inline=True)
            embed.add_field(name="Publish Time", value=result['publish_time'], inline=True)

            embed.set_thumbnail(url=result['thumbnails'][0])
            embed.set_footer(text=f"Requested by {ctx.author}")
            return embed
        
        try:
            result = ytsearch(searchQuery, max_results=10).to_dict()

            embeds = list(map(resultEmbed, result))

            doExit, curPage = False, 0
            await message.add_reaction('🗑️')
            await message.add_reaction('⬇️')
            if len(embeds) > 1:
                await message.add_reaction('◀️')
                await message.add_reaction('▶️')
            elif len(embeds) == 0:
                embed=discord.Embed(description=f'No results found for: {searchQuery}')
                await message.edit(content=None, embed=embed)
                await asyncio.sleep(60)
                await message.delete()
                return
            while doExit == False:
                try:
                    await message.edit(content=None, embed=embeds[curPage%len(embeds)])
                    reaction, user = await bot.wait_for("reaction_add", check=lambda reaction, user: all([str(reaction.emoji) in ["◀️", "▶️", "🗑️", "⬇️"], reaction.message == message, not user.bot]), timeout=60)
                    await message.remove_reaction(reaction, user)
                    if str(reaction.emoji) == '🗑️':
                        await message.delete()
                        doExit = True
                    elif str(reaction.emoji) == '◀️':
                        curPage-=1
                    elif str(reaction.emoji) == '▶️':
                        curPage+=1
                    elif str(reaction.emoji) == '⬇️' and userSettings[user.id]["downloadquota"]["dailyDownload"] < 50:
                        await message.remove_reaction(reaction, bot.user)
                        downloadmessage = await ctx.send(f'{LoadingMessage()}')
                        yt = YoutubeDownload(embeds[curPage].url)
                        download = yt.streams.filter(res='360p', file_extension='mp4', progressive=True).fmt_streams[0]
                        if round(download.filesize_approx/1000000, 2) < 100:
                            embed = discord.Embed(
                                description=f"""{user}, This download will use {round(download.filesize_approx/1000000, 2)}MB of your remaining {50-userSettings[user.id]["downloadquota"]["dailyDownload"]}MB daily quota
                                                Do you want to continue?""")
                            await downloadmessage.edit(content=None, embed=embed)
                            await downloadmessage.add_reaction('👍')
                            await downloadmessage.add_reaction('👎')
                            dlreaction, dluser = await bot.wait_for("reaction_add", check=lambda dlreaction, dluser: all([dluser == user, str(dlreaction.emoji) in ['👍', '👎'], dlreaction.message == downloadmessage]), timeout=30)

                            if str(dlreaction.emoji) == '👍':
                                await downloadmessage.clear_reactions()
                                await downloadmessage.edit(content=f'{LoadingMessage()}', embed=None)
                                
                                userSettings[user.id]['downloadquota']['dailyDownload'] += round(download.filesize_approx/1000000, 2)
                                userSettings[user.id]['downloadquota']['lifetimeDownload'] += round(download.filesize_approx/1000000, 2)
                                download.download(output_path='./src/cache')
                                
                                bestServer = requests.get(url='https://api.gofile.io/getServer').json()['data']['server']

                                with open(f'{os.path.abspath(f"./src/cache/{download.default_filename}")}', 'rb') as f:
                                    url = f'https://{bestServer}.gofile.io/uploadFile'
                                    params = {'expire':round(datetime.timestamp(datetime.now()+timedelta(minutes=10)))}
                                    shareLink = requests.post(url=url, params=params, files={f'@{os.path.abspath(f"./src/cache/{download.default_filename}")}': f}).json()['data']['downloadPage']
                                
                                os.remove(f"./src/cache/{download.default_filename}")
                                embed = discord.Embed(
                                    description=f"""{shareLink}\n\nHere is your download link.
                                    You now have {50-userSettings[user.id]['downloadquota']['dailyDownload']}MB left in your daily quota. 
                                    Negative values mean your daily quota for the next day will be subtracted."""
                                )
                                embed.set_footer(text=f'Requested by {user}')
                                await downloadmessage.delete()
                                await ctx.send(embed=embed, content=None)

                                with open('userSettings.yaml', 'w') as data:
                                    yaml.dump(userSettings, data, allow_unicode=True)
                            elif str(dlreaction.emoji) == '👎':
                                await downloadmessage.delete()
                                await message.add_reaction('⬇️')
                        
                        else:
                            embed = discord.Embed(
                                description=f"""{user}, this download is {round(download.filesize_approx/1000000, 2)}MB, which exceeds the maximum filesize of 100MB. It will not be processed.""")
                            await downloadmessage.edit(content=None, embed=embed)
                            
                except asyncio.TimeoutError:
                    await message.clear_reactions()
                except asyncio.CancelledError:
                    pass
        
        except UserCancel as e:
            await ctx.send(f"Cancelled")
                
        except asyncio.TimeoutError:
            await ctx.send(f"Search timed out. Aborting")

        except Exception as e:
            await ErrorHandler(bot, ctx, e, searchQuery)
        finally: return

class UserCancel(Exception):
    pass