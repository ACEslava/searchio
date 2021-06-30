from fp.fp import FreeProxy
from scholarly import scholarly, ProxyGenerator
from src.utils import Log, ErrorHandler
from itertools import islice
import discord, asyncio, random
import scholarly as scholarlyExceptions
class ScholarSearch:   
    @staticmethod
    async def search(bot, ctx, message, args, searchQuery):
        #region various embed types creation
        def publicationEmbeds(result):
            embed=discord.Embed(title=result['bib']['title'], 
                            description=result['bib']['abstract'], 
                            url=result['eprint_url'] if 'eprint_url' in result.keys() else result['pub_url'])
            embed.add_field(name="Authors", value=', '.join(result['bib']['author']).strip(), inline=True) 
            
            embed.add_field(name="Publisher", value=result['bib']['venue'], inline=True)                
            embed.add_field(name="Publication Year", value=result['bib']['pub_year'], inline=True)
            embed.add_field(name="Cited By", value=result['num_citations'] if 'num_citations' in result.keys() else '0', inline=True)
            
            embed.add_field(name="Related Articles", value=f'https://scholar.google.com{result["url_related_articles"]}', inline=True)

            embed.set_footer(text=f"Requested by {ctx.author}")
            return embed
        
        def authorEmbeds(result):
            embed=discord.Embed(title=result['name'])     
            embed.add_field(name="Cited By", value=f"{result['citedby']} articles", inline=True)                
            embed.add_field(name="Scholar ID", value=result['scholar_id'], inline=True)
            embed.add_field(name="Affiliation", value=result['affiliation'] if 'affiliation' in result.keys() else 'None', inline=True)
            embed.add_field(name="Interests", value=f"{', '.join(result['interests']) if 'interests' in result.keys() else 'None'}", inline=True)
            embed.set_image(url=result['url_picture']) 
            embed.set_footer(text=f"Requested by {ctx.author}")
            return embed
        
        def citationEmbeds(result):
            embed = discord.Embed(title=result['bib']['title'], 
                description=f'```{scholarly.bibtex(result)}```', 
                url=result['eprint_url'] if 'eprint_url' in result.keys() else result['pub_url'])
            embed.set_footer(text=f"Requested by {ctx.author}")
            return embed    
        #endregion
        
        try:
            #region user flags processing
            
            pg = ProxyGenerator()
            proxy = FreeProxy(rand=True, timeout=1, country_id=['BR']).get()
            pg.SingleProxy(http=proxy, https=proxy)
            scholarly.use_proxy(pg)

            #args processing
            if args is None:
                results = [next(scholarly.search_pubs(searchQuery)) for _ in range(5)]
                embeds = list(map(publicationEmbeds, results))
            if 'author' in args:
                results = [next(scholarly.search_author(searchQuery)) for _ in range(5)]
                embeds = list(map(authorEmbeds, results))
            elif 'cite' in args:
                results = scholarly.search_pubs(searchQuery)
                results = [results for _ in range(5)]
                embeds = list(map(citationEmbeds, results))
            else:
                message.edit(content='Invalid flag')
                return
            #endregion

            doExit, curPage = False, 0
            await message.add_reaction('🗑️')
            if len(embeds) > 1:
               await message.add_reaction('◀️')
               await message.add_reaction('▶️')
            
            while doExit == False:
                await message.edit(content=None, embed=embeds[curPage%len(embeds)])
                reaction, user = await bot.wait_for("reaction_add", check=lambda reaction, user: all([user == ctx.author, str(reaction.emoji) in ["◀️", "▶️", "🗑️"], reaction.message == message]), timeout=60)
                await message.remove_reaction(reaction, user)
                
                if str(reaction.emoji) == '🗑️':
                    await message.delete()
                    doExit = True
                elif str(reaction.emoji) == '◀️':
                    curPage-=1
                elif str(reaction.emoji) == '▶️':
                    curPage+=1
               
        except asyncio.TimeoutError: 
            raise
        except asyncio.CancelledError:
            pass
        except scholarlyExceptions._navigator.MaxTriesExceededException:
            await message.edit(content='Google Scholar is currently blocking our requests. Please try again later')
            Log.appendToLog(ctx, f"{ctx.command} error", 'MaxTriesExceededException')
            return

        except Exception as e:
            await ErrorHandler(bot, ctx, e, searchQuery)
        finally: return