from mal import *
from src.utils import Log, ErrorHandler
from src.loadingmessage import LoadingMessage
import discord, asyncio, random

class MyAnimeListSearch:
    def __init__(
        self,
        bot,
        ctx,
        searchQuery = None):

        self.searchQuery = searchQuery
        self.bot = bot
        self.ctx = ctx
    
    async def search(self):
        try:
            msg = [await self.ctx.send(f'{LoadingMessage()} <a:loading:829119343580545074>')]
            await asyncio.sleep(random.uniform(0,1))
            search = AnimeSearch(self.searchQuery)

            Log.appendToLog(self.ctx, "animesearch", self.searchQuery)

            while True:
                result = [[anime for anime in search.results][x:x+10] for x in range(0, len([anime for anime in search.results]), 10)]
                pages = len(result)
                cur_page = 1
                if len(result) != 1:
                    embed=discord.Embed(title=f"Titles matching '{self.searchQuery}'\n Page {cur_page}/{pages}:", description=
                        ''.join([f'[{index}]: {value.title}\n' for index, value in enumerate(result[cur_page-1])]))
                    embed.set_footer(text=f"Requested by {self.ctx.author}")
                    await msg[0].edit(content=None, embed=embed)
                    await self.bot.wait_until_ready()
                    await msg[-1].add_reaction('◀️')
                    await msg[-1].add_reaction('▶️')
                    msg.append(await self.ctx.send("Please choose option or cancel"))
                
                else:
                    embed=discord.Embed(title=f"Titles matching '{self.searchQuery}':", description=
                        ''.join([f'[{index}]: {value.title}\n' for index, value in enumerate(result[0])]))
                    embed.set_footer(text=f"Requested by {self.ctx.author}")
                    msg.append(await self.ctx.send(embed=embed))
                    msg.append(await self.ctx.send("Please choose option or cancel"))

                while True:
                    try: #checks for user input or reaction input.
                        emojitask = asyncio.create_task(self.bot.wait_for("reaction_add", check=lambda reaction, user: user == self.ctx.author and str(reaction.emoji) in ["◀️", "▶️", "🗑️"], timeout=30))
                        responsetask = asyncio.create_task(self.bot.wait_for('message', check=lambda m: m.author == self.ctx.author, timeout=30))
                        waiting = [emojitask,responsetask]
                        done, waiting = await asyncio.wait(waiting, return_when=asyncio.FIRST_COMPLETED) # 30 seconds wait either reply or react
                        
                        if emojitask in done: # if reaction input, change page
                            reaction, user = emojitask.result()
                            if str(reaction.emoji) == "▶️" and cur_page != pages:
                                cur_page += 1
                                embed=discord.Embed(title=f"Titles matching '{self.searchQuery}'\nPage {cur_page}/{pages}:", description=
                                    ''.join([f'[{index}]: {value}\n' for index, value in enumerate(result[cur_page-1])]))
                                embed.set_footer(text=f"Requested by {self.ctx.author}")
                                await msg[-2].edit(embed=embed)
                                await msg[-2].remove_reaction(reaction, user)
                            
                            elif str(reaction.emoji) == "◀️" and cur_page > 1:
                                cur_page -= 1
                                embed=discord.Embed(title=f"Titles matching '{self.searchQuery}'\n Page {cur_page}/{pages}:", description=
                                    ''.join([f'[{index}]: {value}\n' for index, value in enumerate(result[cur_page-1])]))
                                embed.set_footer(text=f"Requested by {self.ctx.author}")
                                await msg[-2].edit(embed=embed)
                                await msg[-2].remove_reaction(reaction, user)
                            
                            else:
                                await msg[-2].remove_reaction(reaction, user)
                                # removes reactions if the user tries to go forward on the last page or
                                # backwards on the first page
                        
                        elif responsetask in done:
                            emojitask.cancel()
                            input = responsetask.result() 
                            await input.delete()
                            if input.content == 'cancel':
                                raise UserCancel
                            elif input.content not in ["0", "1", "2", "3", "4", "5", "6", "7", "8", "9"]:
                                continue
                            input = int(input.content)
                            animeItem = result[cur_page-1][input]
                            
                            embed=discord.Embed(title=f'{animeItem.title}', 
                                description=animeItem.synopsis, 
                                url=animeItem.url) #Myanimelist data
                                
                            embed.add_field(name="MyAnimeListID", value=animeItem.mal_id, inline=True)
                            embed.add_field(name="Rating", value=animeItem.score, inline=True)
                            embed.add_field(name="Episodes", value=animeItem.episodes, inline=True)

                            embed.set_thumbnail(url=animeItem.image_url)
                            embed.set_footer(text=f"Requested by {self.ctx.author}")
                            searchresult = await self.ctx.send(embed=embed)
                            
                            Log.appendToLog(self.ctx, "animesearch result", animeItem.title )
                            for message in msg:
                                await message.delete()
                            
                            try:
                                await searchresult.add_reaction('🗑️')
                                reaction, user = await self.bot.wait_for("reaction_add", check=lambda reaction, user: user == self.ctx.author and str(reaction.emoji) == "🗑️", timeout=60)
                                if str(reaction.emoji) == '🗑️':
                                    await searchresult.delete()
                            
                            except asyncio.TimeoutError as e: 
                                await searchresult.clear_reactions()
                            
                            finally: 
                                return
                    
                    except UserCancel as e:
                        Log.appendToLog(self.ctx, "animesearch cancel")

                        for message in msg:
                            await message.delete()
                    
                    except asyncio.TimeoutError:
                        for message in msg:
                            await message.delete()

                        Log.appendToLog(self.ctx, "animesearch timeout")

                        await self.ctx.send(f"Search timed out. Aborting")

                    except Exception as e:
                        for message in msg:
                            await message.delete()
                    finally:
                        return

        except Exception as e:
            await ErrorHandler(self.bot, self.ctx, e, 'anime', self.searchQuery)
        finally: return

class UserCancel(Exception):
    pass