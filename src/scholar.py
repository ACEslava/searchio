from scholarly import scholarly
from src.utils import Log, ErrorHandler
import discord, asyncio, random

class ScholarSearch:   
    @staticmethod
    async def search(bot, ctx, message, args, searchQuery):
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
        
        def citationEmbeds(result):
            embed = discord.Embed(title=result['bib']['title'], 
                description=f'```{scholarly.bibtex(result)}```', 
                url=result['eprint_url'] if 'eprint_url' in result.keys() else result['pub_url'])
            embed.set_footer(text=f"Requested by {ctx.author}")
            return embed    
        
        try:
            await asyncio.sleep(random.uniform(0,2))
            if 'author' in args:
                results = scholarly.search_pubs(searchQuery)
                results = [next(scholarly.search_author(searchQuery)) for _ in range(5)]
                embeds = list(map(authorEmbeds, results))
            elif 'cite' in args:
                results = scholarly.search_pubs(searchQuery)
                results = [results for _ in range(5)]
                embeds = list(map(citationEmbeds, results))
            else:
                results = [next(scholarly.search_pubs(searchQuery)) for _ in range(5)]
                embeds = list(map(publicationEmbeds, results))

            doExit, curPage = False, 0
            await message.add_reaction('🗑️')
            if len(embeds) > 1:
               await message.add_reaction('◀️')
               await message.add_reaction('▶️')
            
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
               
        except asyncio.TimeoutError: 
            raise

        except Exception as e:
            await ErrorHandler(bot, ctx, e, searchQuery)
        finally: return