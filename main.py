from src.wikipedia import WikipediaSearch
from src.google import GoogleSearch
from src.myanimelist import MyAnimeListSearch
from src.googlereverseimages import ImageSearch
from src.loadingmessage import LoadingMessage
from src.utils import Sudo, Log, ErrorHandler
from src.scholar import ScholarSearch
from src.youtube import YoutubeSearch
from src.xkcd import XKCDSearch
from src.pornhub import PornhubSearch
from dotenv import load_dotenv
from discord.ext import commands
from os import getenv, path
from asyncio import TimeoutError, create_task, wait
from yaml import load, dump, FullLoader
from csv import DictReader, DictWriter
from datetime import datetime, timedelta
from requests import get
from time import sleep
import discord, asyncio, re

#region utility functions
def prefix(bot, message): #handler for individual guild prefixes
    try:
        commandprefix = serverSettings[message.guild.id]['commandprefix']
    except Exception:
        commandprefix = '&'
    finally: return commandprefix

async def searchQueryParse(ctx, args, bot): #handler for bot search queries
    UserCancel = KeyboardInterrupt
    global userSettings
    userSettings = Sudo.userSettingsCheck(userSettings, ctx.author.id)

    if not args: #checks if search is empty
        await ctx.send("Enter search query or cancel") #if empty, asks user for search query
        try:
            userquery = await bot.wait_for('message', check=lambda m: m.author == ctx.author, timeout = 30) # 30 seconds to reply
            userquery = userquery.content
            if userquery.lower() == 'cancel': raise UserCancel

        except TimeoutError:
            await ctx.send(f'{ctx.author.mention} Error: You took too long. Aborting') #aborts if timeout

        except UserCancel:
            await ctx.send('Aborting')
            return
    else: 
        userquery = ' '.join(list(args)).strip() #turns multiword search into single string.

    return userquery
#endregion

def main():
    global serverSettings, userSettings
    #region onlaunch code
    intents = discord.Intents.default()
    intents.members = True
    intents.presences = True

    bot = commands.Bot(command_prefix=prefix, intents=intents, help_command=None)

    #checks if serverSettings.json exists
    if not path.exists('logs.csv'):
        with open('logs.csv', 'w') as file:
            file.write('')

    if not path.exists('serverSettings.yaml'):
        with open('serverSettings.yaml', 'w') as file:
            file.write('')

    if not path.exists('userSettings.yaml'):
        with open('userSettings.yaml', 'w') as file:
            file.write('')

    #loads serverSettings
    with open('serverSettings.yaml', 'r') as data:
        serverSettings = load(data, FullLoader)
        if serverSettings is None: serverSettings = {}

    #loads userSettings
    with open('userSettings.yaml', 'r') as data:
        userSettings = load(data, FullLoader)
        if userSettings is None: userSettings = {}
    #endregion

    @bot.event
    async def on_guild_join(guild):
        #Reads settings of server
        Sudo.settingsCheck(serverSettings, guild.id)

        owner = await bot.fetch_user(guild.owner_id)
        dm = await owner.create_dm()
        appInfo = await bot.application_info()
        try:
            embed = discord.Embed(title=f"Search.io was added to your server: '{guild.name}'.", 
                description = f"""
            Search.io is a bot that searches through multiple search engines/APIs.
            The activation command is '&', and a list of various commands can be found using '&help'.
            
            A list of admin commands can be found by using '&help sudo'. These commands may need ID numbers, which requires Developer Mode.
            To turn on Developer Mode, go to Settings > Appearances > Advanced > Developer Mode. Then right click on users, roles, channels, or guilds to copy their ID.
            If you need to block a specific user from using Search.io, do '&sudo blacklist [userID]'. Unblock with '&sudo whitelist [userID]'

            Guild-specific settings can be accessed with '&config'
            As a start, it is suggested to designate an administrator role that can use Search.io's sudo commands. Do '&config adminrole [roleID]' to designate an admin role.
            You can change the command prefix with '&config prefix [character]'
            You can also block or unblock specific commands with '&config [command]'
            It is also suggested to turn on Safe Search, if needed. Do '&config safesearch'. The default is off. 

            If you have any problems with Search.io, DM {str(appInfo.owner)}""")
            await dm.send(embed=embed)
        except discord.errors.Forbidden:
            pass
        finally: return

    @bot.event
    async def on_guild_remove(guild):
        del serverSettings[guild.id]
        
        with open('serverSettings.yaml', 'w') as data:
            dump(serverSettings, data, allow_unicode=True)
        return

    @bot.event
    async def on_connect():
        global serverSettings
        await bot.change_presence(activity=discord.Activity(type=discord.ActivityType.listening, name="command prefix '&'"))

        appInfo = await bot.application_info()
        bot.owner_id = appInfo.owner.id

        for servers in bot.guilds:
            serverSettings = Sudo.serverSettingsCheck(serverSettings, servers.id, bot)

        with open("logs.csv", "r", newline='', encoding='utf-8-sig') as file:
            lines = [dict(row) for row in DictReader(file) if datetime.utcnow()-datetime.fromisoformat(row["Time"]) < timedelta(weeks=8)]
            
        with open("logs.csv", "w", newline='', encoding='utf-8-sig') as file:
            logFieldnames = ["Time", "Guild", "User", "User_Plaintext", "Command", "Args"]
            writer = DictWriter(file, fieldnames=logFieldnames, extrasaction='ignore')
            writer.writeheader()
            writer.writerows(lines)

        with open('./src/cache/googleUULE.csv', 'w', encoding='utf-8-sig') as file:
            file.write(get('https://developers.google.com/adwords/api/docs/appendix/geo/geotargets-2021-04-16.csv').text)         
        return

    @bot.event
    async def on_command_error(ctx, error):
        if isinstance(error, commands.errors.CommandNotFound):
            await ctx.send(f"Command not found. Do {Sudo.printPrefix(serverSettings, ctx)}help for available commands")

    @bot.command()
    async def help(ctx, *args):
        try:
            def check(reaction, user):
                return user == ctx.author and str(reaction.emoji) in ["🗑️"]
            commandPrefix = Sudo.printPrefix(ctx)
            searchEngineCog = dict(bot.cogs)['Search Engines']
            adminCog = dict(bot.cogs)['Administration']

            maxAdminCommandStrLength = len(max([command.name for command in adminCog.get_commands()], key=len))
            args = list(args)

            embed = discord.Embed(title="SearchIO", 
                description="Search.io is a bot that searches through multiple search engines/APIs.\nIt is developed by ACEslava#9735, K1NG#6219, and Nanu#3294")

            embed.add_field(name="Administration", inline=False, value="\n".join([f'`{command.name:>{maxAdminCommandStrLength}}:` {command.brief}' for command in adminCog.get_commands()]))

            embed.add_field(
                name="Search Engines", 
                inline=False, 
                value='\n'.join([f"`{command.name:>10}:` {command.brief}" 
                    for command in searchEngineCog.get_commands() if serverSettings[ctx.guild.id]['searchEngines'][command.name] == True]))

            embed.set_footer(text=f"Do {commandPrefix}help [command] for more information")

            if args:
                try:
                    command = getattr(searchEngineCog, args[0].lower())
                except AttributeError:
                    try: command = getattr(adminCog, args[0].lower())
                    except AttributeError: command = None

                if command is not None:
                    embed = discord.Embed(title=command.name, 
                        description=f"""
                        {command.help}
                        Usage:
                        ```{command.usage}```
                        {'Optionals:```'+command.description+'```' if command.description != '' else ''}""")
                    embed.set_footer(text=f"Requested by {ctx.author}")
                    helpMessage = await ctx.send(embed=embed)
                    try:
                        await helpMessage.add_reaction('🗑️')
                        reaction, user = await bot.wait_for("reaction_add", check=check, timeout=60)
                        if str(reaction.emoji) == '🗑️':
                            await helpMessage.delete()
                            return

                    except TimeoutError as e: 
                        await helpMessage.clear_reactions()
                else: pass
            else:
                dm = await ctx.author.create_dm()
                await dm.send(embed=embed)
                await dm.send('\n'.join(['If you have further questions, feel free to join the support server: https://discord.gg/YB8VGYMZSQ',
                'Want to add the bot to your server? Use this invite link: https://discord.com/api/oauth2/authorize?client_id=786356027099840534&permissions=4228381776&scope=bot']))

        except discord.errors.Forbidden:
            await ctx.send('Sorry, I cannot open a DM at this time. Please check your privacy settings')
        except Exception as e:
            await ErrorHandler(bot, ctx, e)
        finally: return

    load_dotenv()
    DISCORD_TOKEN = getenv("DISCORD_TOKEN")

    bot.add_cog(SearchEngines(bot))
    bot.add_cog(Administration(bot))

    bot.run(DISCORD_TOKEN)
class SearchEngines(commands.Cog, name="Search Engines"):
    def __init__(self, bot):
        self.bot = bot
    
    async def cog_before_invoke(self, ctx):
        global userSettings
        userSettings = Sudo.userSettingsCheck(userSettings, ctx.author.id)
        if ctx.command.name == 's' and userSettings[ctx.author.id]['searchAlias'] is not None:
            Log.appendToLog(ctx, userSettings[ctx.author.id]['searchAlias'])
        elif ctx.command.name == 's':
            Log.appendToLog(ctx, 's', 'Not set')
        else: Log.appendToLog(ctx)
        return

    @commands.command(
        name = 'wiki',
        brief='Search through Wikipedia.',
        usage='wiki [query] [optional flags]',
        help='Wikipedia search.',
        description='--lang [ISO Language Code]: Specifies a country code to search through Wikipedia. Use wikilang to see available codes.')
    async def wiki(self, ctx, *args):
        global serverSettings
        if Sudo.isAuthorizedCommand(self.bot, ctx, serverSettings):
            UserCancel = Exception
            language = "en"
            if not args: #checks if search is empty
                await ctx.send("Enter search query or cancel") #if empty, asks user for search query
                try:
                    userquery = await self.bot.wait_for('message', check=lambda m: m.author == ctx.author, timeout = 30) # 30 seconds to reply
                    userquery = userquery.content
                    if userquery.lower() == 'cancel': raise UserCancel
                
                except TimeoutError:
                    await ctx.send(f'{ctx.author.mention} Error: You took too long. Aborting') #aborts if timeout

                except UserCancel:
                    await ctx.send('Aborting')
            else: 
                args = list(args)
                if '--lang' in args:
                    language = args[args.index('--lang')+1]
                    del args[args.index('--lang'):]
                userquery = ' '.join(args).strip() #turns multiword search into single string

            search = WikipediaSearch(self.bot, ctx, language, userquery)
            await search.search()
            return
    
    @commands.command(
        name= 'wikilang',
        brief="Lists supported languages for Wikipedia's --lang flag",
        usage='wikilang',
        help="""Lists Wikipedia's supported wikis in ISO codes. Common language codes are:
                    zh: 中文
                    es: Español
                    en: English
                    pt: Português
                    hi: हिन्दी
                    bn: বাংলা
                    ru: русский""")
    async def wikilang(self, ctx):
        global serverSettings
        if Sudo.isAuthorizedCommand(self.bot, ctx, serverSettings):
            await WikipediaSearch(self.bot, ctx, "en").lang()
            return

    @commands.command(
        name= 'google',
        brief='Search through Google',
        usage='google [query]',
        help='Google search. If a keyword is detected in [query], a special function will activate',
        description=''.join(["translate: Uses Google Translate API to translate languages.",
            "\n\n     Input auto detects language unless specified with 'from [language]'", 
            "\n\n     Defaults to output English OR user locale if set, unless explicitly specified with 'to [language]'",
            "\n\n     Example Query: translate مرحبا from arabic to spanish",
            "\n\n\nimage: Searches only for image results.",
            "\n\n\ndefine: Queries dictionaryapi.dev for an English definition of the word"]))
    async def google(self, ctx, *args):
        global serverSettings
        global userSettings

        if Sudo.isAuthorizedCommand(self.bot, ctx, serverSettings):
            userquery = await searchQueryParse(ctx, args, self.bot)
            if userquery is None: return
            continueLoop = True
            while continueLoop:
                try:
                    message = await ctx.send(f'{LoadingMessage()} <a:loading:829119343580545074>')
                    searchClass = GoogleSearch(self.bot, ctx, serverSettings, userSettings, message, userquery)

                    messageEdit = create_task(self.bot.wait_for('message_edit', check=lambda var, m: m.author == ctx.author and m == ctx.message))
                    if bool(re.search('translate', userquery.lower())): 
                        search = create_task(searchClass.translate())
                    
                    elif bool(re.search('define', userquery.lower())):
                        search = create_task(searchClass.define())
                    
                    else: search = create_task(searchClass.search())
                    
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
                        userquery = messageEdit[1].content.replace(f'{prefix(self.bot, message)}google ', '') #finds the new user query
                        continue
                    else: raise TimeoutError
                
                except TimeoutError: #after a minute, everything cancels
                    messageEdit.cancel()
                    search.cancel()
                    continueLoop = False
                    return
                
                except asyncio.CancelledError:
                    pass
                
                except Exception as e:
                    await message.delete()
                    await ErrorHandler(self.bot, ctx, e, userquery)
                    return

    @commands.command(
        name='image',
        brief="Google's Reverse Image Search with an image URL or image reply",
        usage='image [imageURL] OR reply to an image in the chat',
        help="Uses Google's Reverse Image search to output URLs that contain the image")
    async def image(self, ctx, *args):
        global serverSettings
        UserCancel = Exception
        if Sudo.isAuthorizedCommand(self.bot, ctx, serverSettings):
            userquery = await searchQueryParse(ctx, args, self.bot)
            if userquery is None: return

            search = ImageSearch(self.bot, ctx, userquery)
            await search.search()
            return

    @commands.command(
        name= 'scholar',
        brief='Search through Google Scholar',
        usage='scholar [query] [flags]',
        help='Google Scholar search',
        description="""--author: Use [query] to search for a specific author. Cannot be used with --cite
                        --cite: Outputs a citation for [query] in BibTex. Cannot be used with --author""")   
    async def scholar(self, ctx, *args):
        global serverSettings
        if Sudo.isAuthorizedCommand(self.bot, ctx, serverSettings):
            UserCancel = Exception
            if not args: #checks if search is empty
                await ctx.send("Enter search query or cancel") #if empty, asks user for search query
                try:
                    userquery = await self.bot.wait_for('message', check=lambda m: m.author == ctx.author, timeout = 30) # 30 seconds to reply
                    userquery = userquery.content
                    if userquery.lower() == 'cancel': raise UserCancel
                
                except TimeoutError:
                    await ctx.send(f'{ctx.author.mention} Error: You took too long. Aborting') #aborts if timeout

                except UserCancel:
                    await ctx.send('Aborting')
                    return
            else:
                args = ' '.join(list(args)).strip().split('--') #turns entire command into list split by flag operator
                userquery = args[0].strip()
                del args[0]

            continueLoop = True 
            while continueLoop:
                try:
                    message = await ctx.send(f'{LoadingMessage()} <a:loading:829119343580545074>')
                    messageEdit = create_task(self.bot.wait_for('message_edit', check=lambda var, m: m.author == ctx.author and m == ctx.message))
                    search = create_task(ScholarSearch.search(self.bot, ctx, message, args, userquery))
                    
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
                        userquery = messageEdit[1].content.replace(f'{prefix(self.bot, message)}scholar ', '')
                        continue
                    else: raise TimeoutError
                
                except TimeoutError: #after a minute, everything cancels
                    await message.clear_reactions()
                    messageEdit.cancel()
                    search.cancel()
                    continueLoop = False
                    return
                
                except asyncio.CancelledError:
                    pass
                
                except Exception as e:
                    await ErrorHandler(self.bot, ctx, e, userquery)
                    return

    @commands.command(
        name= 'youtube',
        brief='Search through Youtube',
        usage='youtube [query]',
        help='Searches through Youtube videos')
    async def youtube(self, ctx, *args):
        global serverSettings
        global userSettings
        
        UserCancel = Exception
        if Sudo.isAuthorizedCommand(self.bot, ctx, serverSettings):
            userquery = await searchQueryParse(ctx, args, self.bot)
            if userquery is None: return
            continueLoop = True 
            while continueLoop:
                try:
                    message = await ctx.send(f'{LoadingMessage()} <a:loading:829119343580545074>')
                    messageEdit = create_task(self.bot.wait_for('message_edit', check=lambda var, m: m.author == ctx.author and m == ctx.message))
                    search = create_task(YoutubeSearch.search(self.bot, ctx, message, userquery, userSettings))
                    
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
                        userquery = messageEdit[1].content.replace(f'{prefix(self.bot, message)}youtube ', '')
                        continue
                    else: 
                        with open('userSettings.yaml', 'r') as data:
                            userSettings = load(data)
                        raise TimeoutError
                
                except TimeoutError: #after a minute, everything cancels
                    await message.clear_reactions()
                    messageEdit.cancel()
                    search.cancel()
                    continueLoop = False
                    return
                
                except asyncio.CancelledError:
                    pass
                
                except Exception as e:
                    await ErrorHandler(self.bot, ctx, e, userquery)
                    return

    @commands.command(
        name= 'mal',
        brief='Search through MyAnimeList',
        usage='mal [query]',
        help='Searches through MyAnimeList')
    async def mal(self, ctx, *args):
        global serverSettings
        UserCancel = Exception
        if Sudo.isAuthorizedCommand(self.bot, ctx, serverSettings):
            userquery = await searchQueryParse(ctx, args, self.bot)
            if userquery is None: return
            search = MyAnimeListSearch(self.bot, ctx, userquery)
            await search.search()
            return

    @commands.command(
        name='xkcd',
        brief='Search for XKCD comics',
        usage='xkcd [comic# OR random OR latest]',
        help='Searches for an XKCD comic. Search query can be an XKCD comic number, random, or latest.')
    async def xkcd(self, ctx, *args):
        global serverSettings
        UserCancel = Exception
        if Sudo.isAuthorizedCommand(self.bot, ctx, serverSettings):
            userquery = await searchQueryParse(ctx, args, self.bot)
            if userquery is None: return
            await XKCDSearch.search(self.bot, ctx, userquery)
            return

    @commands.command(
        name='pornhub',
        brief='Search through Pornhub',
        usage='pornhub [query]',
        help='Searches for Pornhub videos. Returns a maximum of 10 results')
    async def pornhub(self, ctx, *args):
        global serverSettings
        global userSettings

        userSettings = Sudo.userSettingsCheck(userSettings, ctx.author.id)
        UserCancel = KeyboardInterrupt
        
        if Sudo.isAuthorizedCommand(self.bot, ctx, serverSettings) and ctx.channel.nsfw:
            userquery = await searchQueryParse(ctx, args, self.bot)
            if userquery is None: return
            continueLoop = True
            
            while continueLoop:
                try:
                    message = await ctx.send(f'{LoadingMessage()} <a:loading:829119343580545074>')
                    messageEdit = create_task(self.bot.wait_for('message_edit', check=lambda var, m: m.author == ctx.author and m == ctx.message))
                    search = create_task(PornhubSearch.search(self.bot, ctx, userquery, message))
                    
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
                        userquery = messageEdit[1].content.replace(f'{prefix(self.bot, message)}pornhub ', '')
                        continue
                    else: raise TimeoutError
                
                except TimeoutError: #after a minute, everything cancels
                    messageEdit.cancel()
                    search.cancel()
                    continueLoop = False
                    return
                
                except asyncio.CancelledError:
                    pass
                
                except Exception as e:
                    await ErrorHandler(self.bot, ctx, e, userquery)
                    return

    #alias command (always last)
    @commands.command(
        name='s',
        brief='A shortcut search function',
        usage='s [query]',
        help='A user-settable shortcut for any search function')
    async def s(self, ctx, *args):
        try:
            if userSettings[ctx.author.id]['searchAlias'] is None:
                embed = discord.Embed(description=f'Your shortcut is not set. Set it with {Sudo.printPrefix(serverSettings, ctx)}config alias [Search Engine]')
                message = await ctx.send(embed=embed)
                await message.add_reaction('🗑️')
                reaction, user = await self.bot.wait_for("reaction_add", check=lambda reaction, user: all([user == ctx.author, str(reaction.emoji) == "🗑️", reaction.message == message]), timeout=60)
                if str(reaction.emoji) == '🗑️':
                    await message.delete()           
            else: 
                try:
                    await getattr(SearchEngines, userSettings[ctx.author.id]['searchAlias']).__call__(self, ctx, *args)
                except AttributeError:
                    embed = discord.Embed(description=f'Your shortcut is invalid. The shortcut must be typed exactly as shown in {Sudo.printPrefix(serverSettings, ctx)}help')
                    message = ctx.send(embed=embed)
                    await message.add_reaction('🗑️')
                    reaction, user = await self.bot.wait_for("reaction_add", check=lambda reaction, user: all([user == ctx.author, str(reaction.emoji) == "🗑️", reaction.message == message]), timeout=60)
                    if str(reaction.emoji) == '🗑️':
                        await message.delete()
        except TimeoutError as e: 
                    await message.clear_reactions()
        except Exception as e:
            await ErrorHandler(self.bot, ctx, e, args)
        finally: return

class Administration(commands.Cog, name="Administration"):
    def __init__(self, bot):
        self.bot = bot
    
    async def cog_before_invoke(self, ctx):
        global userSettings
        userSettings = Sudo.userSettingsCheck(userSettings, ctx.author.id)
        return
    
    @commands.command(
        name='log',
        brief='DMs a .csv file of all the logs that the bot has for your username or guild if a sudoer.',
        usage='log')
    async def logging(self, ctx): 
        await Log.logRequest(self.bot, ctx, serverSettings, userSettings)
        return

    @commands.command(
        name='sudo',
        brief='Various admin commands.',
        usage=f'sudo [command] [args]',
        help='Admin commands. Server owner has sudo privilege by default.',
        description=f"""
                echo: Have the bot say something. 
                Args: message 
                Optional flag: --channel [channelID]

                blacklist: Block a user/role from using the bot. 
                Args: userName OR userID OR roleID

                whitelist: Unblock a user/role from using the bot. 
                Args: userName OR userID OR roleID

                sudoer: Add a user to the sudo list. Only guild owners can do this. 
                Args: userName OR userID  

                unsudoer: Remove a user from the sudo list. Only guild owners can do this. 
                Args: userName OR userID""")
    async def sudo(self, ctx, *args):
        global serverSettings
        global userSettings

        if Sudo.isSudoer(self.bot, ctx, serverSettings):
            Log.appendToLog(ctx, None, args)
            command = Sudo(self.bot, ctx, serverSettings, userSettings)
            serverSettings = await command.sudo(list(args))
        else:
            await ctx.send(f"`{ctx.author}` is not in the sudoers file.  This incident will be reported.")
            Log.appendToLog(ctx, None, 'unauthorised')

    @commands.command(
        name='config',
        brief='Views the guild configuration. Only sudoers can edit settings.',
        usage='config [setting] [args]',
        help=f"""Views the configuration menu.

                Guild Configurations:
                ```
                Prefix: Command prefix that SearchIO uses
                Adminrole: The role that is automatically given sudo permissions
                Safesearch: Activates Google's safesearch. NSFW channels override this setting
                
                Guilds can deactivate each search engine if they choose to.
                Requires sudo privileges to edit
                ```
                
                User Configurations:
                ```
                Locale: Sets the user's locale for more accurate Google searches
                Alias: Sets the search function's command to use.""")
    async def config(self, ctx, *args):
        args = list(args)
        global serverSettings
        global userSettings

        command = Sudo(self.bot, ctx, serverSettings, userSettings)
        if len(args) > 0:
            localSetting = args[0] in ['locale', 'alias']
        else: localSetting = False
        
        if Sudo.isSudoer(self.bot, ctx, serverSettings) or localSetting:
            serverSettings, userSettings = await command.config(args)
        
        else: serverSettings, userSettings = await command.config([])
        Log.appendToLog(ctx)

    @commands.command(
        name='invite',
        brief="DMs SearchIO's invite link to the user",
        usage='invite',
        help="DMs SearchIO's invite link to the user")
    async def invite(self, ctx):
        try:
            Log.appendToLog(ctx)
            dm = await ctx.author.create_dm()
            await dm.send('Here ya go: https://discord.com/api/oauth2/authorize?client_id=786356027099840534&permissions=4228381776&scope=bot')
        except discord.errors.Forbidden:
            await ctx.send('Sorry, I cannot open a DM at this time. Please check your privacy settings')
        except Exception as e:
            await ErrorHandler(bot, ctx, e)
        finally: return

    @commands.command(
        name='ping',
        brief="Sends SearchIO's DiscordAPI connection latency",
        usage='ping',
        help="Sends SearchIO's DiscordAPI connection latency")
    async def ping(self, ctx):
        try:
            beforeTime = datetime.now()
            message = await ctx.send('Testing')
            serverLatency = datetime.now() - beforeTime
            embed = discord.Embed(description='\n'.join(
                            [f'Message Send Time: `{round(serverLatency.total_seconds()*1000, 2)}ms`',
                            f'API Heartbeat: `{round(bot.latency, 2)}ms`']))
            embed.set_footer(text=f'Requested by {ctx.author}')
            await message.edit(content=None, embed=embed)
        except Exception as e:
            await ErrorHandler(bot, ctx, e)
        finally: return

while 1:
    try:
        main()
    except Exception:
        sleep(30)
        continue
