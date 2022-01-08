#Utility Modules
from src.loadingmessage import get_loading_message
from src.utils import Sudo, Log, error_handler

#Search Engine Modules
# from src.search_engines.scholar import ScholarSearch
from src.search_engines.finances import FinancialSearch
from src.search_engines.wikipedia import WikipediaSearch
from src.search_engines.google import GoogleSearch
from src.search_engines.myanimelist import MyAnimeListSearch
from src.search_engines.youtube import YoutubeSearch
from src.search_engines.xkcd import XKCDSearch
from src.search_engines.pornhub import PornhubSearch

#Discord 
from discord import Embed
from discord.ext import commands

#External Dependencies
from asyncio import TimeoutError, create_task, wait
from copy import deepcopy
import asyncio

class SearchEngines(commands.Cog, name="Search Engines"):
    def __init__(self, bot):
        self.bot:commands.bot = bot
        return

    async def cog_before_invoke(self, ctx):
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
            return

    @commands.command(
        name = 'wiki',
        brief='Search through Wikipedia.',
        usage='wiki [query] [optional flags]',
        help='Wikipedia search.',
        description='--lang [ISO Language Code]: Specifies a country code to search through Wikipedia. Use wikilang to see available codes.')
    async def wiki(self, ctx, *args):
        await self.genericSearch(ctx, WikipediaSearch, args)  
        return

    @commands.command(
        name= 'google',
        brief='Search through Google',
        usage='google [query]',
        help='Google search. If a keyword is detected in [query], a special function will activate',
        description='\n'.join(["translate: Uses Google Translate API to translate languages.",
            "\n     Input auto detects language unless specified with 'from [language]'", 
            "\n     Defaults to output English OR user locale if set, unless explicitly specified with 'to [language]'",
            "\n     Example Query: translate مرحبا from arabic to spanish",
            "\n\nimage: Searches only for image results.",
            "\n\ndefine: Queries dictionaryapi.dev for an English definition of the word",
            "\n\nweather: Queries openweathermap for weather information at the specified location"]),
        aliases=[
            'g',
            'googel',
            'googlr',
            'googl',
            'gogle',
            'gogl',
            'foogle'
        ])
    @commands.cooldown(1, 3, commands.BucketType.default)
    async def google(self, ctx, *args):
        await self.genericSearch(ctx, GoogleSearch, args)
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

    @commands.command(
        name= 'youtube',
        brief='Search through Youtube',
        usage='youtube [query]',
        help='Searches through Youtube videos')
    async def youtube(self, ctx, *args):
        await self.genericSearch(ctx, YoutubeSearch, args)
        return

    @commands.command(
        name= 'mal',
        brief='Search through MyAnimeList',
        usage='mal [query]',
        help='Searches through MyAnimeList')
    async def mal(self, ctx, *args):
        await self.genericSearch(ctx, MyAnimeListSearch, args)
        return

    @commands.command(
        name='xkcd',
        brief='Search for XKCD comics',
        usage='xkcd [comic# OR random OR latest]',
        help='Searches for an XKCD comic. Search query can be an XKCD comic number, random, or latest.')
    async def xkcd(self, ctx, *args):
        await self.genericSearch(ctx, XKCDSearch, args)
        return

    @commands.command(
        name='pornhub',
        brief='Search through Pornhub',
        usage='pornhub [query]',
        help='Searches for Pornhub videos. Returns a maximum of 10 results')
    @commands.is_nsfw()
    async def pornhub(self, ctx, *args):
        await self.genericSearch(ctx, PornhubSearch, args)
        return

    @commands.command(
        name='finance',
        brief='Search for financial data',
        usage='finance [type] [type args]',
        help="""For more info, do finance help [type]
        
        Types:
        `stock [ticker] [range] [interval] [display] [moving average values]`""")   
    async def finance(self, ctx, *args):
        args = list(args)
        if args[0] == 'help' or len(args) == 1:
            if len(args) == 1:
                helpmessage = Embed(
                    title='finance',
                    description=ctx.command.help
                )

            elif args[1] == 'stock':
                helpmessage = Embed(
                    title='Stock',
                    description="""
                finance stock [ticker] [range] [interval] [display] [moving average values]
                
                Ex: finance stock AAPL 1y 1d candle 2 3 5
                Example creates a candle chart displaying 1 year of AAPL with 1 day data points and MAV lines of 2, 3, and 5 days.
                """)
                helpmessage.add_field(name='ticker', value='Symbol')
                helpmessage.add_field(name='range', value='Length of time for data')
                helpmessage.add_field(name='interval', value='Time between data points')
                helpmessage.add_field(name='display', value='candle OR line')
                helpmessage.add_field(name='moving average values', value='number of days for a simple moving average line')  

            await ctx.send(embed=helpmessage)
            try:
                resp = await self.bot.wait_for(
                    "button_click",
                    check=lambda b_ctx: Sudo.pageTurnCheck(
                        bot=self.bot,
                        ctx=ctx,
                        button_ctx=b_ctx,
                        message=helpmessage
                    ),
                    timeout=60
                )

                if str(resp.custom_id) == "🗑️":
                    await helpmessage.delete()
                    return

            except TimeoutError:
                await helpmessage.edit(
                    components=[]
                )
                return
        else:
            await self.genericSearch(ctx, FinancialSearch, args)
    #alias command (always last)
    @commands.command(
        name='s',
        brief='A shortcut search function',
        usage='s [query]',
        help='A user-settable shortcut for any search function')
    async def s(self, ctx, *args):
        await ctx.send(embed=
            Embed(
                description="""The alias system is now deprecated due to interference with other features.
                As an alternative, &google can now be accessed with &g. Sorry for the inconvenience."""
            )
        )
        return
        # try:
        #     if self.bot.userSettings[ctx.author.id]['searchAlias'] is None:
        #         embed = discord.Embed(description=f'Your shortcut is not set. React with 🔍 to set it now')
        #         message = await ctx.send(embed=embed)
        #         await message.add_reaction('🗑️')
        #         await message.add_reaction('🔍')
        #         reaction, _ = await self.bot.wait_for("reaction_add", check=lambda reaction, user: all([user == ctx.author, str(reaction.emoji) in ['🔍', '🗑️'], reaction.message == message]), timeout=60)

        #         if str(reaction.emoji) == '🗑️':
        #             await message.delete() 
        #             return  
        #         elif str(reaction.emoji) == '🔍':  
        #             await getattr(Administration, 'config').__call__(self, ctx, ('alias'))
        #             await message.delete()      

        #     await getattr(SearchEngines, self.bot.userSettings[ctx.author.id]['searchAlias']).__call__(self, ctx, *args)
        # except AttributeError:
        #     embed = discord.Embed(description=f'Your shortcut is invalid. The shortcut must be typed exactly as shown in {Sudo.print_prefix(self.bot.serverSettings, ctx)}help')
        #     message = ctx.send(embed=embed)
        #     await message.add_reaction('🗑️')
        #     reaction, _ = await self.bot.wait_for("reaction_add", check=lambda reaction, user: all([user == ctx.author, str(reaction.emoji) == "🗑️", reaction.message == message]), timeout=60)
        #     if str(reaction.emoji) == '🗑️':
        #         await message.delete()
        # except TimeoutError as e: 
        #             await message.clear_reactions()
        # except Exception as e:
        #     await error_handler(self.bot, ctx, e, args)
        # finally: return

    # @commands.Cog.listener()
    # async def on_message(self, message):
    #     if random.random() <= 0.5: return
    #     user_intent = self.bot.IntentClassifier.get_intent(message.content)
    #     print(user_intent)
    #     if user_intent == 'oos':
    #         msg = await message.channel.send(
    #             embed=discord.Embed(
    #                 title='[BETA] SearchIO Automatic Query Detection',
    #                 description='SearchIO detected a possible search query. Press to search google'),
    #             components=[[
    #                 Button(style=ButtonStyle.green, label=f"🔎", custom_id="search")
    #             ]]
    #         )
    #         resp = await self.bot.wait_for(
    #             "button_click",
    #             check=lambda b_ctx: b_ctx.user.id == message.author.id,
    #             timeout=60,
    #         )
    #         await msg.delete()

    #         if resp.custom_id == 'search':
    #             message.content = f'&g {message.content}'
    #             await self.bot.process_commands(message)
    #         return
        
    async def genericSearch(self, ctx:commands.context, searchObject, args:list) -> None:
        '''A generic search handler for bot search functions.
        
        Args:
            ctx: discord.commands.context
            searchObject: function
            args: list
        
        Raises:
            None
        
        Returns:
            None
        '''
        if Sudo.is_authorized_command(self.bot, ctx):
            # region args parsing
            UserCancel = KeyboardInterrupt
            if not args: #checks if search is empty
                await ctx.send("Enter search query or cancel") #if empty, asks user for search query
                try:
                    userquery = await self.bot.wait_for('message', check=lambda m: m.author == ctx.author, timeout = 30) # 30 seconds to reply
                    if userquery.content.lower() == 'cancel': raise UserCancel
                    else: userquery = userquery.content.split('--')

                except TimeoutError:
                    await ctx.send(f'{ctx.author.mention} Error: You took too long. Aborting') #aborts if timeout

                except UserCancel:
                    await ctx.send('Aborting')
                    return
            else: 
                userquery = ' '.join([query.strip() for query in list(args)]).split('--') #turns multiword search into single string.

            if len(userquery) > 1:
                args = userquery[1:]
            else:
                args = None

            userquery = userquery[0]
            #check if user actually searched something
            if userquery is None: return
            #endregion

            #allows users to edit their search query after results are returned
            continueLoop = True 
            while continueLoop:
                try:
                    message = await ctx.send(get_loading_message())
                    messageEdit = create_task(
                        self.bot.wait_for(
                            'message_edit', 
                            check=lambda var, m: m.author == ctx.author and m == ctx.message
                        )
                    )

                    search = create_task(
                        searchObject(
                            bot=self.bot, 
                            ctx=ctx,
                            server_settings=self.bot.serverSettings,
                            user_settings=self.bot.userSettings,
                            message=message, 
                            args=args, 
                            query=userquery, 
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
                    await message.clear_reactions()
                    messageEdit.cancel()
                    search.cancel()
                    continueLoop = False
                    return

                except Exception as e:
                    await error_handler(self.bot, ctx, e, userquery)
                    return
        return

def setup(bot):
    bot.add_cog(SearchEngines(bot))
    return