from bs4 import BeautifulSoup
from src.utils import Log, ErrorHandler
import requests, discord, random, asyncio

class ImageSearch:
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
            headers = {
                        'Host': 'www.google.com',
                        'User-Agent': 'Mozilla/5.0 (Windows NT 10.0; Win64; x64; rv:71.0) Gecko/20100101 Firefox/71.0',
                        'Accept': '*/*',
                        'Accept-Language': 'en-US,en;q=0.5',
                        'Accept-Encoding': 'identity',
                        'Referer': 'https://www.google.com/',
                        'Origin': 'https://www.google.com',
                        'Connection': 'keep-alive',
                        'Content-Length': '0',
                        'TE': 'Trailers'
                    }

            r = requests.get(#initial search
                f"https://www.google.com/searchbyimage?image_url={self.searchQuery}", 
                headers=headers)

            if r.status_code == 200:
                soup = BeautifulSoup(r.text, "lxml")
                a = soup.find("a", text="All sizes")
                await asyncio.sleep(random.uniform(0,1)) #prevent captcha.
                if a:
                    r = requests.get( #similar images
                        f"https://www.google.com/{a['href']}",
                        headers=headers
                    )
                    
                    soup = BeautifulSoup(r.text, "lxml")
                    div = soup.find("div", attrs={'id':'is-results'})
                    children = div.findChildren("img", recursive=True)
                    urls = [] 
                    for child in children[:5]:
                        urls.append(child.parent.parent.nextSibling.attrs["href"])

                    embed=discord.Embed(title=f"Google Reverse Image Search", description =
                        ''.join([f"{i} \n" for i in urls])
                    )   
                    embed.set_footer(text=f"Requested by {self.ctx.author}")
                    embed.set_thumbnail(url=self.searchQuery)
                    
                    result = await self.ctx.send(embed=embed)

                    Log.appendToLog(self.ctx, f"{self.ctx.command} result", f"{self.searchQuery}")

                    def check(reaction, user):
                        return user == self.ctx.author and str(reaction.emoji) in ["🗑️"]
                    
                    try:
                        await result.add_reaction('🗑️')
                        reaction, user = await self.bot.wait_for("reaction_add", check=check, timeout=60)
                        if str(reaction.emoji) == '🗑️':
                            await result.delete()
                    
                    except asyncio.TimeoutError as e: 
                        await result.clear_reactions()
        
                else:
                    embed=discord.Embed(title=f"Google Reverse Image Search", description = "No similar images found")  
                    embed.set_footer(text=f"Requested by {self.ctx.author}")
                    embed.set_thumbnail(url=self.searchQuery)

                    result = await self.ctx.send(embed=embed)

                    Log.appendToLog(self.ctx, f"{self.ctx.command} result", f"no similar images")

                    def check(reaction, user):
                        return user == self.ctx.author and str(reaction.emoji) in ["🗑️"]
                    
                    try:
                        await result.add_reaction('🗑️')
                        reaction, user = await self.bot.wait_for("reaction_add", check=check, timeout=60)
                        if str(reaction.emoji) == '🗑️':
                            await result.delete()

                    except asyncio.TimeoutError as e: 
                        await result.clear_reactions()

            else:
                await self.ctx.send("Google is currently blocking searches. Please try again later")
        
        except Exception as e:
            await ErrorHandler(self.bot, self.ctx, e, self.searchQuery)
        finally: return