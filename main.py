import discord, os, asyncio, json, yaml, textwrap, csv, datetime, requests
from src.wikipedia import WikipediaSearch
from src.google import GoogleSearch
from src.myanimelist import MyAnimeListSearch
from src.googlereverseimages import ImageSearch
from src.loadingmessage import LoadingMessage
from src.utils import Sudo, Log, ErrorHandler
from src.scholar import ScholarSearch
from src.youtube import YoutubeSearch
from src.xkcd import XKCDSearch
from dotenv import load_dotenv
from discord.ext import commands
from urllib3 import PoolManager

load_dotenv()
DISCORD_TOKEN = os.getenv("DISCORD_TOKEN")

#checks if serverSettings.json exists
if not os.path.exists('serverSettings.yaml'):
    with open('serverSettings.yaml', 'w') as file:
        file.write('---')

if not os.path.exists('userSettings.yaml'):
    with open('userSettings.yaml', 'w') as file:
        file.write('---')

#loads serverSettings
with open('serverSettings.yaml', 'r') as data:
    serverSettings = yaml.load(data)

#loads userSettings
with open('userSettings.yaml', 'r') as data:
    userSettings = yaml.load(data)

def prefix(bot, message):
    try:
        commandprefix = serverSettings[message.guild.id]['commandprefix']
    except Exception:
        commandprefix = '&'
    finally: return commandprefix

intents = discord.Intents.default()
intents.members = True
intents.presences = True

bot = commands.Bot(command_prefix=prefix, intents=intents, help_command=None)
http = PoolManager()
async def searchQueryParse(ctx, args):
    UserCancel = Exception
    global userSettings
    userSettings = Sudo.userSettingsCheck(userSettings, ctx.author.id)

    if not args: #checks if search is empty
        await ctx.send("Enter search query or cancel") #if empty, asks user for search query
        try:
            userquery = await bot.wait_for('message', check=lambda m: m.author == ctx.author, timeout = 30) # 30 seconds to reply
            userquery = userquery.content
            if userquery.lower() == 'cancel': raise UserCancel
        
        except asyncio.TimeoutError:
            await ctx.send(f'{ctx.author.mention} Error: You took too long. Aborting') #aborts if timeout

        except UserCancel:
            await ctx.send('Aborting')
            return
    else: 
        userquery = ' '.join(list(args)).strip() #turns multiword search into single string.

    return userquery

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
        yaml.dump(serverSettings, data, allow_unicode=True)
    return

@bot.event
async def on_connect():
    global serverSettings
    await bot.change_presence(activity=discord.Activity(type=discord.ActivityType.listening, name="command prefix '&'"))

    appInfo = await bot.application_info()
    bot.owner_id = appInfo.owner.id

    for servers in bot.guilds:
        serverSettings = Sudo.serverSettingsCheck(serverSettings, servers.id)
    
    with open('serverSettings.yaml', 'w') as data:
        yaml.dump(serverSettings, data, allow_unicode=True)

    with open("logs.csv", "r", newline='', encoding='utf-8-sig') as file:
        lines = [dict(row) for row in csv.DictReader(file) if datetime.datetime.utcnow()-datetime.datetime.fromisoformat(row["Time"]) < datetime.timedelta(weeks=8)]
        
    with open("logs.csv", "w", newline='', encoding='utf-8-sig') as file:
        logFieldnames = ["Time", "Guild", "User", "User_Plaintext", "Command", "Args"]
        writer = csv.DictWriter(file, fieldnames=logFieldnames, extrasaction='ignore')
        writer.writeheader()
        writer.writerows(lines)

    with open('./src/cache/googleUULE.csv', 'w', encoding='utf-8-sig') as file:
        file.write(requests.get('https://developers.google.com/adwords/api/docs/appendix/geo/geotargets-2021-04-16.csv').text)           
    return

@bot.event
async def on_command_error(ctx, error):
    if isinstance(error, discord.ext.commands.errors.CommandNotFound):
        await ctx.send(f"Command not found. Do {Sudo.printPrefix(serverSettings, ctx)}help for available commands")

class SearchEngines(commands.Cog, name="Search Engines"):
    def __init__(self, bot):
        self.bot = bot

    @commands.command(
        name = 'wiki',
        brief='Search through Wikipedia.',
        usage='wiki [query] [optional flags]',
        help='Wikipedia search.',
        description='--lang [ISO Language Code]: Specifies a country code to search through Wikipedia. Use wikilang to see available codes.')
    async def wikipedia(self, ctx, *args):
        global serverSettings
        blacklist = ctx.author.id not in serverSettings[ctx.guild.id]['blacklist'] and not any(role.id in serverSettings[ctx.guild.id]['blacklist'] for role in ctx.author.roles)
        if (blacklist and serverSettings[ctx.guild.id]['wikipedia'] != False) or Sudo.isSudoer(bot, ctx, serverSettings):
            UserCancel = Exception
            language = "en"
            if not args: #checks if search is empty
                await ctx.send("Enter search query or cancel") #if empty, asks user for search query
                try:
                    userquery = await bot.wait_for('message', check=lambda m: m.author == ctx.author, timeout = 30) # 30 seconds to reply
                    userquery = userquery.content
                    if userquery.lower() == 'cancel': raise UserCancel
                
                except asyncio.TimeoutError:
                    await ctx.send(f'{ctx.author.mention} Error: You took too long. Aborting') #aborts if timeout

                except UserCancel:
                    await ctx.send('Aborting')
            else: 
                args = list(args)
                if '--lang' in args:
                    language = args[args.index('--lang')+1]
                    del args[args.index('--lang'):]
                userquery = ' '.join(args).strip() #turns multiword search into single string

            search = WikipediaSearch(bot, ctx, language, userquery)
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
        blacklist = ctx.author.id not in serverSettings[ctx.guild.id]['blacklist'] and not any(role.id in serverSettings[ctx.guild.id]['blacklist'] for role in ctx.author.roles)
        if (blacklist and serverSettings[ctx.guild.id]['wikipedia'] != False) or Sudo.isSudoer(bot, ctx, serverSettings):
            Log.appendToLog(ctx, 'wikilang')

            await WikipediaSearch(bot, ctx, "en").lang()
            return

    @commands.command(
        name= 'google',
        brief='Search through Google',
        usage='google [query]',
        help='Google search. If a keyword is detected in [query], a special function will activate',
        description=''.join(["translate: Uses Google Translate API to translate languages.",
            "Input automatically detects language unless specified with 'from [language]'", 
            "Defaults to output English unless specified with 'to [language]'",
            "Example Query: translate مرحبا from arabic to spanish"]))
    async def google(self, ctx, *args):
        global serverSettings
        UserCancel = Exception
        blacklist = ctx.author.id not in serverSettings[ctx.guild.id]['blacklist'] and not any(role.id in serverSettings[ctx.guild.id]['blacklist'] for role in ctx.author.roles)
        if (blacklist and serverSettings[ctx.guild.id]['google'] != False) or Sudo.isSudoer(bot, ctx, serverSettings):
            userquery = await searchQueryParse(ctx, args)
            if userquery is None: return
            continueLoop = True
            
            while continueLoop:
                try:
                    message = await ctx.send(f'{LoadingMessage()} <a:loading:829119343580545074>')
                    messageEdit = asyncio.create_task(self.bot.wait_for('message_edit', check=lambda var, m: m.author == ctx.author and m == ctx.message))
                    search = asyncio.create_task(GoogleSearch.search(http, bot, ctx, serverSettings, userSettings, message, userquery))
                    
                    #checks for message edit
                    waiting = [messageEdit, search]
                    done, waiting = await asyncio.wait(waiting, return_when=asyncio.FIRST_COMPLETED)

                    if messageEdit in done: #if the message is edited, the search is cancelled, message deleted, and command is restarted
                        if type(messageEdit.exception()) == asyncio.TimeoutError:
                            raise asyncio.TimeoutError
                        await message.delete()
                        messageEdit.cancel()
                        search.cancel()

                        messageEdit = messageEdit.result()
                        userquery = messageEdit[1].content.replace(f'{prefix(bot, message)}google ', '')
                        continue
                    else: raise asyncio.TimeoutError
                
                except asyncio.TimeoutError: #after a minute, everything cancels
                    await message.clear_reactions()
                    messageEdit.cancel()
                    search.cancel()
                    continueLoop = False
                    return
                
                except asyncio.CancelledError:
                    pass
                
                except Exception as e:
                    await ErrorHandler(bot, ctx, e, 'google', userquery)
                    return

    @commands.command(
        name='image',
        brief="Google's Reverse Image Search with an image URL or image reply",
        usage='image [imageURL] OR reply to an image in the chat',
        help="Uses Google's Reverse Image search to output URLs that contain the image")
    async def image(self, ctx, *args):
        global serverSettings
        UserCancel = Exception
        blacklist = ctx.author.id not in serverSettings[ctx.guild.id]['blacklist'] and not any(role.id in serverSettings[ctx.guild.id]['blacklist'] for role in ctx.author.roles)
        if (blacklist and serverSettings[ctx.guild.id]['google'] != False) or Sudo.isSudoer(bot, ctx, serverSettings):
            userquery = await searchQueryParse(ctx, args)
            if userquery is None: return

            search = ImageSearch(bot, ctx, userquery)
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
        blacklist = ctx.author.id not in serverSettings[ctx.guild.id]['blacklist'] and not any(role.id in serverSettings[ctx.guild.id]['blacklist'] for role in ctx.author.roles)
        if (blacklist and serverSettings[ctx.guild.id]['scholar'] != False) or Sudo.isSudoer(bot, ctx, serverSettings):
            UserCancel = Exception
            if not args: #checks if search is empty
                await ctx.send("Enter search query or cancel") #if empty, asks user for search query
                try:
                    userquery = await bot.wait_for('message', check=lambda m: m.author == ctx.author, timeout = 30) # 30 seconds to reply
                    userquery = userquery.content
                    if userquery.lower() == 'cancel': raise UserCancel
                
                except asyncio.TimeoutError:
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
                    messageEdit = asyncio.create_task(self.bot.wait_for('message_edit', check=lambda var, m: m.author == ctx.author and m == ctx.message))
                    search = asyncio.create_task(ScholarSearch.search(bot, ctx, message, args, userquery))
                    
                    #checks for message edit
                    waiting = [messageEdit, search]
                    done, waiting = await asyncio.wait(waiting, return_when=asyncio.FIRST_COMPLETED)

                    if messageEdit in done: #if the message is edited, the search is cancelled, message deleted, and command is restarted
                        if type(messageEdit.exception()) == asyncio.TimeoutError:
                            raise asyncio.TimeoutError
                        await message.delete()
                        messageEdit.cancel()
                        search.cancel()

                        messageEdit = messageEdit.result()
                        userquery = messageEdit[1].content.replace(f'{prefix(bot, message)}scholar ', '')
                        continue
                    else: raise asyncio.TimeoutError
                
                except asyncio.TimeoutError: #after a minute, everything cancels
                    await message.clear_reactions()
                    messageEdit.cancel()
                    search.cancel()
                    continueLoop = False
                    return
                
                except asyncio.CancelledError:
                    pass
                
                except Exception as e:
                    await ErrorHandler(bot, ctx, e, 'scholar', userquery)
                    return

    @commands.command(
        name= 'youtube',
        brief='Search through Youtube',
        usage='youtube [query]',
        help='Searches through Youtube videos')
    async def youtube(self, ctx, *args):
        global serverSettings
        UserCancel = Exception
        blacklist = ctx.author.id not in serverSettings[ctx.guild.id]['blacklist'] and not any(role.id in serverSettings[ctx.guild.id]['blacklist'] for role in ctx.author.roles)
        if (blacklist and serverSettings[ctx.guild.id]['google'] != False) or Sudo.isSudoer(bot, ctx, serverSettings):
            userquery = await searchQueryParse(ctx, args)
            if userquery is None: return
            continueLoop = True 
            while continueLoop:
                try:
                    message = await ctx.send(f'{LoadingMessage()} <a:loading:829119343580545074>')
                    messageEdit = asyncio.create_task(self.bot.wait_for('message_edit', check=lambda var, m: m.author == ctx.author and m == ctx.message))
                    search = asyncio.create_task(YoutubeSearch.search(bot, ctx, message, userquery))
                    
                    #checks for message edit
                    waiting = [messageEdit, search]
                    done, waiting = await asyncio.wait(waiting, return_when=asyncio.FIRST_COMPLETED)

                    if messageEdit in done: #if the message is edited, the search is cancelled, message deleted, and command is restarted
                        if type(messageEdit.exception()) == asyncio.TimeoutError:
                            raise asyncio.TimeoutError
                        await message.delete()
                        messageEdit.cancel()
                        search.cancel()

                        messageEdit = messageEdit.result()
                        userquery = messageEdit[1].content.replace(f'{prefix(bot, message)}youtube ', '')
                        continue
                    else: raise asyncio.TimeoutError
                
                except asyncio.TimeoutError: #after a minute, everything cancels
                    await message.clear_reactions()
                    messageEdit.cancel()
                    search.cancel()
                    continueLoop = False
                    return
                
                except asyncio.CancelledError:
                    pass
                
                except Exception as e:
                    await ErrorHandler(bot, ctx, e, 'youtube', userquery)
                    return

    @commands.command(
        name= 'anime',
        brief='Search through MyAnimeList',
        usage='anime [query]',
        help='Searches through MyAnimeList')
    async def anime(self, ctx, *args):
        global serverSettings
        UserCancel = Exception
        blacklist = ctx.author.id not in serverSettings[ctx.guild.id]['blacklist'] and not any(role.id in serverSettings[ctx.guild.id]['blacklist'] for role in ctx.author.roles)
        if (blacklist and serverSettings[ctx.guild.id]['mal'] != False) or Sudo.isSudoer(bot, ctx, serverSettings):
            userquery = await searchQueryParse(ctx, args)
            if userquery is None: return
            search = MyAnimeListSearch(bot, ctx, userquery)
            await search.search()
            return

    @commands.command(
        name= 'xkcd',
        brief='Search for XKCD comics',
        usage='xkcd [comic# OR random OR latest]',
        help='Searches for an XKCD comic. Search query can be an XKCD comic number, random, or latest.')
    async def xkcd(self, ctx, *args):
        global serverSettings
        UserCancel = Exception
        blacklist = ctx.author.id not in serverSettings[ctx.guild.id]['blacklist'] and not any(role.id in serverSettings[ctx.guild.id]['blacklist'] for role in ctx.author.roles)
        if (blacklist and serverSettings[ctx.guild.id]['xkcd'] != False) or Sudo.isSudoer(bot, ctx, serverSettings):
            userquery = await searchQueryParse(ctx, args)
            if userquery is None: return
            await XKCDSearch.search(bot, ctx, userquery)
            return
class Administration(commands.Cog, name="Administration"):
    def __init__(self, bot):
        self.bot = bot
    
    @commands.command(
        name='log',
        brief='DMs a .csv file of all the logs that the bot has for your username or guild if a sudoer.',
        usage='log')
    async def logging(self, ctx): 
        Log.appendToLog(ctx, 'log')
        await Log.logRequest(bot, ctx, serverSettings)
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

        args = list(args)
        if Sudo.isSudoer(bot, ctx, serverSettings) == False:
            await ctx.send(f"`{ctx.author}` is not in the sudoers file.  This incident will be reported.")
            Log.appendToLog(ctx, 'sudo', 'unauthorised')
        else:
            Log.appendToLog(ctx, "sudo", ' '.join(args).strip())
            command = Sudo(bot, ctx, serverSettings)
            serverSettings = await command.sudo(args)

    @commands.command(
        name='config',
        brief='Views the guild configuration. Only sudoers can edit settings.',
        usage='config [setting] [args]',
        help="""Views the guild configuration. Requires sudo privileges to edit settings,
                Prefix: Command prefix that SearchIO uses
                Adminrole: The role that is automatically given sudo permissions
                Safesearch: Activates Google's safesearch. NSFW channels override this setting""")
    async def config(self, ctx, *args):
        args = list(args)
        global serverSettings
        global userSettings

        command = Sudo(bot, ctx, serverSettings, userSettings)
        if len(args) > 0:
            localSetting = args[0] in ['locale']
        else: localSetting = False
        
        if Sudo.isSudoer(bot, ctx, serverSettings) == True or localSetting:
            serverSettings, userSettings = await command.config(args)
        
        else: serverSettings, userSettings = await command.config([])
        
        Log.appendToLog(ctx, 'config', args if len(args) > 0 else None)

    @commands.command(
        name='invite',
        brief="DMs SearchIO's invite link to the user",
        usage='invite',
        help="DMs SearchIO's invite link to the user")
    async def invite(self, ctx):
        try:
            dm = await ctx.author.create_dm()
            await dm.send('Here ya go: https://discord.com/api/oauth2/authorize?client_id=786356027099840534&permissions=4228381776&scope=bot')
        except discord.errors.Forbidden:
            await ctx.send('Sorry, I cannot open a DM at this time. Please check your privacy settings')
        except Exception as e:
            await ErrorHandler(bot, ctx, e, 'help')
        finally: return

    @commands.command(
        name='ping',
        brief="Sends SearchIO's DiscordAPI connection latency",
        usage='ping',
        help="Sends SearchIO's DiscordAPI connection latency")
    async def ping(self, ctx):
        try:
            await ctx.send(f'Response in {round(bot.latency, 3)}ms')
        except Exception as e:
            await ErrorHandler(bot, ctx, e, 'ping')
        finally: return

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
        
        embed.add_field(name="Search Engines", inline=False, value=textwrap.dedent(f"""\
            {f"`wikipedia:` {searchEngineCog.wikipedia.brief}" if serverSettings[ctx.guild.id]['wikipedia'] == True else ''}
            {f"` wikilang:` {searchEngineCog.wikilang.brief}" if serverSettings[ctx.guild.id]['wikipedia'] == True else ''}
            {f"`   google:` {searchEngineCog.google.brief}" if serverSettings[ctx.guild.id]['google'] == True else ''}
            {f"`    image:` {searchEngineCog.image.brief}" if serverSettings[ctx.guild.id]['google'] == True else ''}
            {f"`  scholar:` {searchEngineCog.scholar.brief}" if serverSettings[ctx.guild.id]['scholar'] == True else ''}
            {f"`  youtube:` {searchEngineCog.youtube.brief}" if serverSettings[ctx.guild.id]['youtube'] == True else ''}
            {f"`    anime:` {searchEngineCog.anime.brief}" if serverSettings[ctx.guild.id]['mal'] == True else ''}
            {f"`     xkcd:` {searchEngineCog.xkcd.brief}" if serverSettings[ctx.guild.id]['xkcd'] == True else ''}
        """))
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
                
                except asyncio.TimeoutError as e: 
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
        await ErrorHandler(bot, ctx, e, 'help')
    finally: return

bot.add_cog(SearchEngines(bot))
bot.add_cog(Administration(bot))

bot.run(DISCORD_TOKEN)
