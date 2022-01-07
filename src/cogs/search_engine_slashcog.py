#Discord
from discord import Embed
from discord.ext import commands
from discord_slash import cog_ext
from discord_slash.utils.manage_commands import create_option, create_choice

#Utility Modules
from src.loadingmessage import get_loading_message
from src.utils import Sudo, Log, error_handler

#Search Engine Modules
from src.search_engines.wikipedia import WikipediaSearch
from src.search_engines.google import GoogleSearch
from src.search_engines.myanimelist import MyAnimeListSearch
from src.search_engines.scholar import ScholarSearch
from src.search_engines.youtube import YoutubeSearch
from src.search_engines.xkcd import XKCDSearch
from src.search_engines.pornhub import PornhubSearch

#External Dependencies
from asyncio import TimeoutError, create_task, wait
from copy import deepcopy
from yaml import load, FullLoader
import asyncio

with open('serverSettings.yaml', 'r') as data:
    guild_ids = [int(x,0) for x in list(load(data, FullLoader).keys())]

class SearchEnginesSlash(commands.Cog, name="Search Engines Slash"):
    def __init__(self, bot):
        self.bot = bot
        return

    @cog_ext.cog_slash(
        name = 'wiki',
        description='Search through Wikipedia.',
        options=[create_option(
            name='query',
            description='Search query',
            option_type=3,
            required=True
        )])
    async def wiki(self, ctx, query:str):
        await self.genericSearch(ctx, WikipediaSearch, query)  
        return

    @cog_ext.cog_slash(
        name = 'google',
        description='Search through Google.',
        options=[
            create_option(
                name='query',
                description='Search query',
                option_type=3,
                required=True
            ),
            create_option(
                name='special',
                description='Special functions',
                option_type=3,
                required=False,
                choices=[
                    create_choice(
                        name='define',
                        value='define'
                    ),
                    create_choice(
                        name='weather',
                        value='weather'
                    )
                ]
            )
        ])
    @commands.cooldown(1, 3, commands.BucketType.default)
    async def google(self, ctx, query:str, special:str=None):
        await self.genericSearch(ctx, GoogleSearch, query, special)
        return

    @cog_ext.cog_slash(
        name = 'translate',
        description='Use Google Translate',
        options=[
            create_option(
                name='query',
                description='Thing to translate',
                option_type=3,
                required=True
            ),
            create_option(
                name='language_to',
                description='Language to translate into',
                option_type=3,
                required=True
            ),
            create_option(
                name='language_from',
                description='Language to translate from',
                option_type=3,
                required=False
            )
        ])
    @commands.cooldown(1, 3, commands.BucketType.default)
    async def translate(self, ctx, query:str, language_to:str, language_from:str=None):
        query = f'translate {query}{f" from {language_from}" if language_from is not None else ""} to {language_to}'
        await self.genericSearch(ctx, GoogleSearch, query, 'translate')
        return

    # @commands.command(
    #     name= 'scholar',
    #     brief='Search through Google Scholar',
    #     usage='scholar [query] [flags]',
    #     help='Google Scholar search',
    #     description="""--author: Use [query] to search for a specific author. Cannot be used with --cite
    #                     --cite: Outputs a citation for [query] in BibTex. Cannot be used with --author""",
    #     enabled=False)   
    # async def scholar(self, ctx, *args):
    #     await self.genericSearch(ctx, ScholarSearch, args)
    #     return

    # @commands.command(
    #     name= 'youtube',
    #     brief='Search through Youtube',
    #     usage='youtube [query]',
    #     help='Searches through Youtube videos')
    # async def youtube(self, ctx, *args):
    #     await self.genericSearch(ctx, YoutubeSearch, args)
    #     return

    # @commands.command(
    #     name= 'mal',
    #     brief='Search through MyAnimeList',
    #     usage='mal [query]',
    #     help='Searches through MyAnimeList')
    # async def mal(self, ctx, *args):
    #     await self.genericSearch(ctx, MyAnimeListSearch, args)
    #     return

    # @commands.command(
    #     name='xkcd',
    #     brief='Search for XKCD comics',
    #     usage='xkcd [comic# OR random OR latest]',
    #     help='Searches for an XKCD comic. Search query can be an XKCD comic number, random, or latest.')
    # async def xkcd(self, ctx, *args):
    #     await self.genericSearch(ctx, XKCDSearch, args)
    #     return

    # @commands.command(
    #     name='pornhub',
    #     brief='Search through Pornhub',
    #     usage='pornhub [query]',
    #     help='Searches for Pornhub videos. Returns a maximum of 10 results')
    # @commands.is_nsfw()
    # async def pornhub(self, ctx, *args):
    #     await self.genericSearch(ctx, PornhubSearch, args)
    #     return

    async def genericSearch(self, ctx, searchObject, query:str, optionals:str=None):
        if Sudo.is_authorized_command(self.bot, ctx):
            old_userSettings = deepcopy(self.bot.userSettings)
            self.bot.userSettings = Sudo.user_settings_check(self.bot.userSettings, ctx.author.id)
            if old_userSettings != self.bot.userSettings:
                Sudo.save_configs(self.bot)

            #Leveling system
            self.bot.userSettings[ctx.author.id]['level']['xp'] += 1
            if self.bot.userSettings[ctx.author.id]['level']['xp'] >= self.bot.userSettings[ctx.author.id]['level']['rank']*10:
                self.bot.userSettings[ctx.author.id]['level']['xp'] = 0
                self.bot.userSettings[ctx.author.id]['level']['rank'] += 1

                Sudo.save_configs(self.bot)

                await ctx.send(
                    embed=Embed(
                        description=f"Congratulations {ctx.author}, you are now level {self.bot.userSettings[ctx.author.id]['level']['rank']}"
                    )
                )

            # if ctx.command.name == 's' and self.bot.userSettings[ctx.author.id]['searchAlias'] is not None:
            #     Log.append_to_log(ctx, self.bot.userSettings[ctx.author.id]['searchAlias'])
            # elif ctx.command.name == 's':
            #     Log.append_to_log(ctx, 's', 'Not set')
            # else:
            Log.append_to_log(ctx)
            
            #allows users to edit their search query after results are returned
            continueLoop = True 
            while continueLoop:
                try:
                    message = await ctx.send(content=get_loading_message())
                    messageEdit = create_task(self.bot.wait_for('message_edit', check=lambda var, m: m.author == ctx.author and m == ctx.message))

                    search = create_task(
                        searchObject(
                            bot=self.bot, 
                            ctx=ctx,
                            server_settings=self.bot.serverSettings,
                            user_settings=self.bot.userSettings,
                            message=message, 
                            args=optionals.split(' ') if optionals is not None else [], 
                            query=query, 
                        )()
                    )

                    #checks for message edit
                    waiting = [messageEdit, search]
                    done, waiting = await wait(waiting, return_when=asyncio.FIRST_COMPLETED)

                    if messageEdit in done: #if the message is edited, the search is cancelled, message deleted, and command is restarted
                        if type(messageEdit.exception()) == TimeoutError:
                            raise TimeoutError
                        await message.delete()
                        messageEdit.cancel()
                        search.cancel()

                        messageEdit = messageEdit.result()
                        userquery = messageEdit[1].content.replace(f'{Sudo.print_prefix(self.bot.serverSettings, ctx)}{ctx.invoked_with} ', '') #finds the new user query
                        continue
                    else: raise TimeoutError

                except TimeoutError: #after a minute, everything cancels
                    await message.edit(
                        components=[]
                    )
                    messageEdit.cancel()
                    search.cancel()
                    continueLoop = False
                    return

                except Exception as e:
                    await error_handler(self.bot, ctx, e, userquery)
                    return

def setup(bot):
    bot.add_cog(SearchEnginesSlash(bot))
    return