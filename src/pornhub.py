from pornhub_api import PornhubApi
from discord import Embed
from src.utils import ErrorHandler
import asyncio

class PornhubSearch():
    @staticmethod
    async def search(bot, ctx, searchQuery, message):
        def videoEmbed(video):
            embed = Embed(title=video.title)
            embed.add_field(name='Video ID', value=video.video_id)
            embed.add_field(name='Views', value=video.views)
            embed.add_field(name='Rating', value=video.rating)
            embed.add_field(name='Pornstars', 
                value=', '.join([pornstar.pornstar_name for pornstar in video.pornstars]) if video.pornstars != [] else 'None listed')
            embed.add_field(name='Publish Date', value=video.publish_date.strftime('%m/%d/%Y'))
            embed.add_field(name='Duration', value=video.duration)
            embed.add_field(name='Tags', 
                value=', '.join([tag.tag_name for tag in video.tags] if video.tags != [] else 'None listed'),
                inline=False)
           
            embed.set_thumbnail(url=f'{video.default_thumb.scheme}://{video.default_thumb.host}/{video.default_thumb.path}')
            embed.url=f'{video.url.scheme}://{video.url.host}{video.url.path}?viewkey={video.video_id}'
            return embed
        try:
            data = PornhubApi().search.search(searchQuery).videos[0:10]
            embeds = list(map(videoEmbed, data))

            for index, item in enumerate(embeds): 
                item.set_footer(text=f'Page {index+1}/{len(embeds)}\nRequested by: {str(ctx.author)}')

            doExit, curPage = False, 0
            await message.add_reaction('🗑️')
            if len(embeds) > 1:
                await message.add_reaction('◀️')
                await message.add_reaction('▶️')
            
            while doExit == False:
                try:
                    await message.edit(content=None, embed=embeds[curPage])
                    reaction, user = await bot.wait_for("reaction_add", check=lambda reaction, user: all([user == ctx.author, str(reaction.emoji) in ["◀️", "▶️", "🗑️"], reaction.message == message]), timeout=60)
                    await message.remove_reaction(reaction, user)
                    if str(reaction.emoji) == '🗑️':
                        await message.delete()
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
                    raise
        except asyncio.TimeoutError:
            raise

        except Exception as e:
            await message.delete()
            await ErrorHandler(bot, ctx, e, searchQuery)
        finally: return
