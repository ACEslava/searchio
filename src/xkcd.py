import json
import urllib.request as ureq
import discord, asyncio, random, datetime, difflib
from src.utils import Log, ErrorHandler
from src.loadingmessage import LoadingMessage

class xkcd:
    def __init__(self, num = ''):
        base_url = 'https://xkcd.com/'
        
        if num.lower() == 'random':
            self.num = random.randrange(1, xkcd('').num)
        elif str(num).isnumeric() or num == '':
            self.num = num
        elif num.lower() == 'latest':
            self.num = xkcd('').num
        else:
            raise ValueError
        
        self.url = base_url + str(self.num)
        json_url = self.url + '/info.0.json'
        
        mdata = json.load(ureq.urlopen(json_url))
        self.date = datetime.datetime(int(mdata['year']), int(mdata['month']), int(mdata['day']))
        self.img_url = mdata['img']
        self.title = mdata['title']
        self.alt = mdata['alt']
        self.num = mdata['num']

class XKCDSearch:
    @staticmethod
    async def search(bot, ctx, searchQuery):
        def check(reaction, user):
            return user == ctx.author and str(reaction.emoji) in ["🗑️"]

        Log.appendToLog(ctx, "xkcd", searchQuery)
        message = await ctx.send(f'{LoadingMessage()} <a:loading:829119343580545074>')
        errorCount = 0
        while errorCount <= 1:
            try:
                x = xkcd(searchQuery)
                embed = discord.Embed(title=x.title, description=x.alt, timestamp=x.date)
                embed.url = x.url
                embed.set_image(url=x.img_url)
                embed.set_footer(text=f"Requested by {ctx.author}")

                await message.edit(content=None, embed=embed)
                Log.appendToLog(ctx, "xkcd", x.url)

                await message.add_reaction('🗑️')
                reaction, user = await bot.wait_for("reaction_add", check=check, timeout=60)
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

            except Exception as e:
                await ErrorHandler(bot, ctx, e, 'youtube', searchQuery)
                return

class UserCancel(Exception):
    pass
