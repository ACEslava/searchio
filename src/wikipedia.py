from src.utils import Log, ErrorHandler
from src.loadingmessage import LoadingMessage
import wikipedia, discord, asyncio, random

class WikipediaSearch:
    def __init__(
        self,
        bot,
        ctx,
        message,
        args,
        searchQuery = None):

        self.searchQuery = searchQuery
        self.bot = bot
        self.ctx = ctx
        self.message = message

        if args is None:
            wikipedia.set_lang('en')
        elif any('lang' in i for i in args):
            language = args[[idx for idx, s in enumerate(args) if 'lang' in s][0]].replace('lang ', '')
            wikipedia.set_lang(language)
    
    async def search(self):
        def searchPages(result):
            return discord.Embed(title=f"Titles matching '{self.searchQuery}'", description=
                ''.join([f'[{index}]: {value}\n' for index, value in enumerate(result)]))
            
        try:
            msg = [self.message]

            #searches
            result = wikipedia.search(self.searchQuery)

            while 1:
                result = [result[x:x+10] for x in range(0, len(result), 10)]
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
                                try:
                                    emojitask.cancel()
                                    input = responsetask.result() 
                                    await input.delete()
                                    if input.content.lower() == 'cancel':
                                        raise UserCancel

                                    input = int(input.content)
                                
                                except ValueError or IndexError:
                                    await msg[-1].edit(content='Invalid choice. Please choose a number between 0-9 or cancel')
                                    continue

                                try:
                                    self.searchQuery = result[curPage][input]
                                    page = wikipedia.WikipediaPage(title=self.searchQuery)
                                    summary = page.summary[:page.summary.find('. ')+1]
                                    embed=discord.Embed(title=f'Wikipedia Article: {page.original_title}', description=summary, url=page.url) #outputs wikipedia article
                                    embed.set_footer(text=f"Requested by {self.ctx.author}")
                                    
                                    for message in msg:
                                        await message.delete()
                                    
                                    msg[0] = await self.ctx.send(embed=embed)
                                    await msg[0].add_reaction('🗑️')
                                    await self.bot.wait_for("reaction_add", 
                                        check=lambda reaction, user: all([user == self.ctx.author, str(reaction.emoji) == "🗑️", reaction.message == msg[0]]), 
                                        timeout=10)
                                    
                                    await msg[0].delete() 
                                    return

                                except wikipedia.DisambiguationError as e:
                                    result = str(e).split('\n')
                                    result.pop(0)
                                    for index, message in enumerate(msg):
                                        await message.delete()
                                    msg = [await self.ctx.send(f'{LoadingMessage()}')]
                                    break
                            
                            except asyncio.TimeoutError:
                                await msg[0].clear_reactions()
                                return
                
                    except UserCancel or asyncio.TimeoutError:
                        for message in msg:
                            await message.delete()
                        return
                    
                    except asyncio.CancelledError:
                        pass

                    except Exception as e:
                        for message in msg:
                            await message.delete()
                        raise

        except Exception as e:
            await ErrorHandler(self.bot, self.ctx, e, self.searchQuery)
        finally: return

    async def lang(self):
        def langPages(languageStr):
            embed = discord.Embed(title=f'Wikipedia Languages', description=languageStr)
            embed.set_footer(text=f"Requested by {self.ctx.author}")
            return embed
        
        try:
            #Multiple page system
            languages = list(wikipedia.languages().items())
            languageStr = [''.join('{c}: {l}\n'.format(c=code, l=lang) for code, lang in languages[x:x+10]) for x in range(0, len(languages), 10)]
            curPage = 0
            embeds = list(map(langPages, languageStr))
            for index, item in enumerate(embeds): 
                item.set_footer(text=f'Page {index+1}/{len(embeds)}\nRequested by: {str(self.ctx.author)}')

            msg = await self.ctx.send(embed=embeds[curPage])
            await msg.add_reaction('🗑️')
            await msg.add_reaction('◀️')
            await msg.add_reaction('▶️')
            
            doExit = False
            while doExit==False:
                try:
                    await msg.edit(content=None, embed=embeds[curPage])
                    reaction, user = await self.bot.wait_for("reaction_add", 
                        timeout=30, 
                        check=lambda reaction, user: user == self.ctx.author and str(reaction.emoji) in ['◀️', '▶️', '🗑️'])
                    # waiting for a reaction to be added - times out after 30 seconds
                    
                    await msg.remove_reaction(reaction, user)
                    if str(reaction.emoji) == '🗑️':
                        await msg.delete()
                        doExit = True
                    elif str(reaction.emoji) == '◀️':
                        curPage-=1
                    elif str(reaction.emoji) == '▶️':
                        curPage+=1

                    if curPage < 0:
                        curPage = len(embeds)-1
                    elif curPage > len(embeds)-1:
                        curPage = 0

                except asyncio.TimeoutError:
                    await msg.clear_reactions()
                    break
                
                except asyncio.CancelledError:
                    pass
        
        except Exception as e:
                await ErrorHandler(self.bot, self.ctx, e)
        finally: return

class UserCancel(Exception):
    pass