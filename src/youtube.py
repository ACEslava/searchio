from youtube_search import YoutubeSearch as ytsearch
from src.utils import Log, ErrorHandler
import discord, asyncio, random

class YoutubeSearch:   
    @staticmethod
    async def search(bot, ctx, message, searchQuery): 
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
            await asyncio.sleep(random.uniform(0,2))
            result = ytsearch(searchQuery, max_results=10).to_dict()

            embeds = list(map(resultEmbed, result))

            doExit, curPage = False, 0
            await message.add_reaction('🗑️')
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
                await message.edit(content=None, embed=embeds[curPage])
                reaction, user = await bot.wait_for("reaction_add", check=lambda reaction, user: all([user == ctx.author, str(reaction.emoji) in ["◀️", "▶️", "🗑️"], reaction.message == message]), timeout=60)
                if str(reaction.emoji) == '🗑️':
                    await message.delete()
                    doExit = True
                elif str(reaction.emoji) == '◀️':
                    curPage-=1
                elif str(reaction.emoji) == '▶️':
                    curPage+=1

                await message.remove_reaction(reaction, user)
                if curPage < 0:
                    curPage = len(embeds)-1
                elif curPage > len(embeds)-1:
                    curPage = 0
        
        except UserCancel as e:
            await ctx.send(f"Cancelled")
            return
                
        except asyncio.TimeoutError:
            await ctx.send(f"Search timed out. Aborting")
            return

        except Exception as e:
            await ErrorHandler(bot, ctx, e, searchQuery)
        finally: return

class UserCancel(Exception):
    pass