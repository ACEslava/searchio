from mal import *
from src.utils import Log, ErrorHandler
from src.loadingmessage import LoadingMessage
import discord, asyncio, random

class MyAnimeListSearch:
    def __init__(
        self,
        bot,
        ctx,
        message,
        searchQuery = None):

        self.searchQuery = searchQuery
        self.bot = bot
        self.ctx = ctx
        self.message = message
    
    async def search(self):
        def searchPages(result):
            return discord.Embed(title=f"Titles matching '{self.searchQuery}'", description=
                ''.join([f'[{index}]: {value.title}\n' for index, value in enumerate(result)]))
        try:
            msg = [self.message]
            await asyncio.sleep(random.uniform(0,1))
            search = AnimeSearch(self.searchQuery)

            while 1:
                result = [[anime for anime in search.results][x:x+10] for x in range(0, len([anime for anime in search.results]), 10)]
                embeds = list(map(searchPages, result))
                curPage = 0

                for index, item in enumerate(embeds): 
                    item.set_footer(text=f'Page {index+1}/{len(embeds)}\nRequested by: {str(self.ctx.author)}')

                await msg[0].add_reaction('🗑️')
                if len(embeds) > 1:
                    await msg[0].add_reaction('◀️')
                    await msg[0].add_reaction('▶️')
                msg.append(await self.ctx.send('Please choose option or cancel'))

                while 1:
                    try:
                        await msg[0].edit(content=None, embed=embeds[curPage%len(embeds)])
                        emojitask = asyncio.create_task(self.bot.wait_for("reaction_add", 
                            check=lambda reaction, user: all([user == self.ctx.author, str(reaction.emoji) in ["◀️", "▶️", "🗑️"], reaction.message == msg[0]]), 
                            timeout=60))
                        responsetask = asyncio.create_task(self.bot.wait_for('message', check=lambda m: m.author == self.ctx.author, timeout=30))
                        
                        waiting = [emojitask, responsetask]
                        done, waiting = await asyncio.wait(waiting, return_when=asyncio.FIRST_COMPLETED) # 30 seconds wait either reply or react
                        if emojitask in done: 
                            reaction, user = emojitask.result()   
                            await msg[0].remove_reaction(reaction, user)
                            
                            if str(reaction.emoji) == '🗑️':
                                await msg[0].delete()
                                return
                            elif str(reaction.emoji) == '◀️':
                                curPage-=1
                            elif str(reaction.emoji) == '▶️':
                                curPage+=1
                        
                        elif responsetask in done:
                            try:
                                emojitask.cancel()
                                input = responsetask.result() 
                                await input.delete()
                                if input.content.lower() == 'cancel':
                                    raise UserCancel
                                input = int(input.content)
                                animeItem = result[curPage][input]
                                
                                embed=discord.Embed(title=f'{animeItem.title}', 
                                    description=animeItem.synopsis, 
                                    url=animeItem.url) #Myanimelist data
                                    
                                embed.add_field(name="MyAnimeListID", value=animeItem.mal_id, inline=True)
                                embed.add_field(name="Rating", value=animeItem.score, inline=True)
                                embed.add_field(name="Episodes", value=animeItem.episodes, inline=True)

                                embed.set_thumbnail(url=animeItem.image_url)
                                embed.set_footer(text=f"Requested by {self.ctx.author}")
                                searchresult = await self.ctx.send(embed=embed)
                                
                                Log.appendToLog(self.ctx, f"{self.ctx.command} result", animeItem.title )
                                for message in msg:
                                    await message.delete()
                            
                                await searchresult.add_reaction('🗑️')
                                reaction, user = await self.bot.wait_for("reaction_add", check=lambda reaction, user: user == self.ctx.author and str(reaction.emoji) == "🗑️", timeout=60)
                                if str(reaction.emoji) == '🗑️':
                                    await searchresult.delete()
                                return
                            
                            except ValueError or IndexError:
                                await msg[-1].edit(content='Invalid choice. Please choose a number between 0-9 or cancel')
                                continue

                            except asyncio.TimeoutError as e: 
                                await searchresult.clear_reactions()
                                return
                            
                            except asyncio.CancelledError:
                                pass
                    
                    except UserCancel as e:

                        for message in msg:
                            await message.delete()
                    
                    except asyncio.TimeoutError:
                        for message in msg:
                            await message.delete()
                    
                    except asyncio.CancelledError:
                        pass

                        await self.ctx.send(f"Search timed out. Aborting")

                    except Exception as e:
                        for message in msg:
                            await message.delete()
        except Exception as e:
            await ErrorHandler(self.bot, self.ctx, e, self.searchQuery)
        finally: return

class UserCancel(Exception):
    pass