from src.utils import Log, ErrorHandler
from src.loadingmessage import LoadingMessage
import wikipedia, discord, asyncio, random

class WikipediaSearch:
    def __init__(
        self,
        bot,
        ctx,
        language,
        searchQuery = None):

        self.searchQuery = searchQuery
        self.bot = bot
        self.ctx = ctx
        wikipedia.set_lang(language)
    
    async def search(self):
        try:
            msg = [await self.ctx.send(f'{LoadingMessage()} <a:loading:829119343580545074>')]

            await asyncio.sleep(random.uniform(0,2))
            result = wikipedia.search(self.searchQuery)

            Log.appendToLog(self.ctx, "wikisearch", self.searchQuery)

            while True:
                result = [result[x:x+10] for x in range(0, len(result), 10)]
                pages = len(result)
                cur_page = 1
                if len(result) == 0:
                    embed=discord.Embed(description=f"No results found for '{self.searchQuery}'")
                    await message.send(embed=embed)

                    try:
                        await message.add_reaction('🗑️')
                        reaction, user = await self.bot.wait_for("reaction_add", check=lambda reaction, user: all([user == self.ctx.author, str(reaction.emoji) == "🗑️", reaction.message == message]), timeout=60)
                        if str(reaction.emoji) == '🗑️':
                            await message.delete()
                    
                    except asyncio.TimeoutError: 
                        await searchresult.clear_reactions()
                    
                    except Exception as e:
                        ErrorHandler(self.bot, self.ctx, e, 'wiki', self.searchQuery)
                    finally: return
                elif len(result) != 1:
                    embed=discord.Embed(title=f"Titles matching '{self.searchQuery}'\n Page {cur_page}/{pages}:", description=
                        ''.join([f'[{index}]: {value}\n' for index, value in enumerate(result[cur_page-1])]))
                    embed.set_footer(text=f"Requested by {self.ctx.author}")
                    await msg[0].edit(content=None, embed=embed)
                    await self.bot.wait_until_ready()
                    await msg[-1].add_reaction('◀️')
                    await msg[-1].add_reaction('▶️')
                    msg.append(await self.ctx.send("Please choose option or cancel"))
                
                else:
                    embed=discord.Embed(title=f"Titles matching '{self.searchQuery}':", description=
                        ''.join([f'[{index}]: {value}\n' for index, value in enumerate(result[0])]))
                    embed.set_footer(text=f"Requested by {self.ctx.author}")
                    await msg[0].edit(content=None, embed=embed)
                    msg.append(await self.ctx.send("Please choose option or cancel"))

                while 1:
                    try: #checks for user input or reaction input.
                        emojitask = asyncio.create_task(self.bot.wait_for("reaction_add", check=lambda reaction, user: all([user == self.ctx.author, str(reaction.emoji) in ["◀️", "▶️", "🗑️"], reaction.message == message]), timeout=30))
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
                            try:
                                self.searchQuery = result[cur_page-1][input]
                                page = wikipedia.WikipediaPage(title=self.searchQuery)
                                summary = page.summary[:page.summary.find('. ')+1]
                                embed=discord.Embed(title=f'Wikipedia Article: {page.original_title}', description=summary, url=page.url) #outputs wikipedia article
                                embed.set_footer(text=f"Requested by {self.ctx.author}")
                                searchresult = await self.ctx.send(embed=embed)
                                
                                Log.appendToLog(self.ctx, "wikisearch result", f"{page.original_title}")

                                try:
                                    for message in msg:
                                        await message.delete()
                                except:
                                    pass
                                
                                try:
                                    await searchresult.add_reaction('🗑️')
                                    reaction, user = await self.bot.wait_for("reaction_add", check=lambda reaction, user: all([user == self.ctx.author, str(reaction.emoji) == "🗑️", reaction.message == searchresult]), timeout=60)
                                    if str(reaction.emoji) == '🗑️':
                                        await searchresult.delete()
                                        return
                                
                                except asyncio.TimeoutError: 
                                    await searchresult.clear_reactions()

                            except wikipedia.DisambiguationError as e:
                                result = str(e).split('\n')
                                result.pop(0)

                                for index, message in enumerate(msg):
                                    await message.delete()
                                    msg.pop(index)
                                break  

                    except UserCancel as e:
                        Log.appendToLog(self.ctx, "wikisearch cancel")

                        for message in msg:
                            await message.delete()
                    
                    except asyncio.TimeoutError:
                        for message in msg:
                            await message.delete()

                        Log.appendToLog(self.ctx, "wikisearch timeout")

                        await self.ctx.send(f"Search timed out. Aborting")

                    except Exception as e:
                        for message in msg:
                            await message.delete()
                    finally:    
                        return

        except Exception as e:
                await ErrorHandler(self.bot, self.ctx, e, 'wiki', self.searchQuery)
        finally: return

    async def lang(self):
        try:
            #Multiple page system
            languages = list(wikipedia.languages().items())
            languages = [languages[x:x+10] for x in range(0, len(languages), 10)]
            for index1, content in enumerate(languages):
                for index2, codes in enumerate(content):
                    content[index2] = ': '.join(codes) + '\n'
                languages[index1] = ''.join([i for i in content])
            pages = len(languages)
            cur_page = 1
            embed = discord.Embed(title=f'Page {cur_page}/{pages}', description=languages[cur_page-1])
            embed.set_footer(text=f"Requested by {self.ctx.author}")
            msg = await self.ctx.send(embed=embed)
            await self.bot.wait_until_ready()
            await msg.add_reaction('◀️')
            await msg.add_reaction('▶️')
            
            def check(reaction, user):
                return user == self.ctx.author and str(reaction.emoji) in ["◀️", "▶️"]
            
            while True:
                try:
                    reaction, user = await self.bot.wait_for("reaction_add", timeout=15, check=check)
                    # waiting for a reaction to be added - times out after 30 seconds

                    if str(reaction.emoji) == "▶️" and cur_page != pages:
                        cur_page += 1
                        embed = discord.Embed(title=f'Page {cur_page}/{pages}', description=languages[cur_page-1])
                        embed.set_footer(text=f"Requested by {self.ctx.author}")
                        await msg.edit(embed=embed)
                        await msg.remove_reaction(reaction, user)
                    
                    elif str(reaction.emoji) == "◀️" and cur_page > 1:
                        cur_page -= 1
                        embed = discord.Embed(title=f'Page {cur_page}/{pages}', description=languages[cur_page-1])
                        embed.set_footer(text=f"Requested by {self.ctx.author}")
                        await msg.edit(embed=embed)
                        await msg.remove_reaction(reaction, user)
                    
                    else:
                        await msg.remove_reaction(reaction, user)
                        # removes reactions if the user tries to go forward on the last page or
                        # backwards on the first page
                except asyncio.TimeoutError:
                    await msg.delete()
                    break
        
        except Exception as e:
                await ErrorHandler(self.bot, self.ctx, e, 'wikilang', '')
        finally: return

class UserCancel(Exception):
    pass