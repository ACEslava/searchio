import json
import urllib.request as ureq
import discord, asyncio, random, datetime, difflib
from src.utils import Log, ErrorHandler
from src.loadingmessage import LoadingMessage

class xkcd:
    def __init__(self, num = ''): 
        if num.lower() == 'random':
            self.num = random.randrange(1, xkcd('').num)
        elif str(num).isnumeric() or num == '':
            self.num = num
        elif num.lower() == 'latest':
            self.num = xkcd('').num
        else:
            raise ValueError
        
        self.url = 'https://xkcd.com/' + str(self.num)
      
        mdata = json.load(ureq.urlopen(self.url + '/info.0.json'))
        self.date = datetime.datetime(int(mdata['year']), int(mdata['month']), int(mdata['day']))
        self.img_url = mdata['img']
        self.title = mdata['title']
        self.alt = mdata['alt']
        self.num = mdata['num']

class XKCDSearch:
    @staticmethod
    async def search(bot, ctx, searchQuery, message):
        errorCount = 0
        while errorCount <= 1:
            try:
                x = xkcd(searchQuery)
                embed = discord.Embed(title=x.title, description=x.alt, timestamp=x.date)
                embed.url = x.url
                embed.set_image(url=x.img_url)
                embed.set_footer(text=f"Requested by {ctx.author}")

                await message.edit(content=None, embed=embed)
                Log.appendToLog(ctx, f"{ctx.command} result", x.url)

                await message.add_reaction('🗑️')
                reaction, user = await bot.wait_for("reaction_add", check=lambda reaction, user: all([user == ctx.author, str(reaction.emoji) == "🗑️", reaction.message == message]), timeout=60)
                if str(reaction.emoji) == '🗑️':
                    await message.delete()
                return

            except UserCancel as e:
                await ctx.send(f"Cancelled")
                return

            except ValueError:
                errorMsg = await ctx.send("Invalid input, an XKCD comic number is needed. Please edit your search or try again.")

                messageEdit = asyncio.create_task(bot.wait_for('message_edit', check=lambda var, m: m.author == ctx.author, timeout=60))
                reply = asyncio.create_task(bot.wait_for('message', check=lambda m: m.author == ctx.author, timeout=60))
                
                waiting = [messageEdit, reply]
                done, waiting = await asyncio.wait(waiting, return_when=asyncio.FIRST_COMPLETED) # 30 seconds wait either reply or react
                if messageEdit in done:
                    reply.cancel()
                    messageEdit = messageEdit.result()
                    searchQuery = ''.join([li for li in difflib.ndiff(messageEdit[0].content, messageEdit[1].content) if '+' in li]).replace('+ ', '')
                elif reply in done:
                    messageEdit.cancel()
                    reply = reply.result()
                    await reply.delete()
                    
                    if reply.content == "cancel":
                        messageEdit.cancel()
                        reply.cancel()
                        break
                    else: searchQuery = reply.content
                await errorMsg.delete()
                errorCount += 1
                continue

            except asyncio.TimeoutError:
                return
            
            except asyncio.CancelledError:
                pass

            except Exception as e:
                await ErrorHandler(bot, ctx, e, searchQuery)
                return

class UserCancel(Exception):
    pass
