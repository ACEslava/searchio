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
import discord, os, asyncio, json, textwrap, difflib

load_dotenv()
DISCORD_TOKEN = os.getenv("DISCORD_TOKEN")

#checks if serverSettings.json exists
if not os.path.exists('serverSettings.json'):
    with open('serverSettings.json', 'w') as file:
        file.write('{}')

#loads serverSettings
with open('serverSettings.json', 'r') as data:
    serverSettings = json.load(data, object_hook=lambda d: {int(k) if k.isdigit() else k: v for k, v in d.items()})

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

@bot.event
async def on_guild_join(guild):
    #Reads settings of server
    Sudo.settingsCheck(serverSettings, guild.id)

    owner = await bot.fetch_user(guild.owner_id)
    dm = await owner.create_dm()
    appInfo = await bot.application_info()

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
    return

@bot.event
async def on_guild_remove(guild):
    del serverSettings[guild.id]
    
    with open('serverSettings.json', 'w') as data:
        data.write(json.dumps(serverSettings, indent=4))
    return

@bot.event
async def on_connect():
    global serverSettings
    await bot.change_presence(activity=discord.Activity(type=discord.ActivityType.listening, name="command prefix '&'"))

    appInfo = await bot.application_info()
    bot.owner_id = appInfo.owner.id

    for servers in bot.guilds:
        serverSettings = Sudo.settingsCheck(serverSettings, servers.id)
    
    with open('serverSettings.json', 'w') as data:
        data.write(json.dumps(serverSettings, indent=4))
    return

@bot.event
async def on_command_error(ctx, error):
    if isinstance(error, discord.ext.commands.errors.CommandNotFound):
        await ctx.send(f"Command not found. Do {Sudo.printPrefix(serverSettings, ctx)}help for available commands")

@bot.command()
async def help(ctx, *args):
    try:
        def check(reaction, user):
            return user == ctx.author and str(reaction.emoji) in ["🗑️"]
        commandPrefix = Sudo.printPrefix(ctx)
        args = list(args)
        
        embed = discord.Embed(title="Help", 
            description="Search.io is a bot that searches through multiple search engines/APIs.\nIt is developed by ACEslava#9735, K1NG#6219, and Nanu#3294")
        
        embed.add_field(name="Administration", inline=False, value=textwrap.dedent(f"""\
            `  sudo:` Various admin commands. Usage: {commandPrefix}sudo [command] [args].
            `  logs:` DMs a .csv of personal logs or guild logs if user is a sudoer. Usage: {commandPrefix}log
            `config:` Views the guild settings. Requires sudo privileges to edit settings
        """))
        
        embed.add_field(name="Search Engines", inline=False, value=textwrap.dedent(f"""\
            {"`wikipedia:` Search through Wikipedia." if serverSettings[ctx.guild.id]['wikipedia'] == True else ''}
            {"` wikilang:` Lists supported languages for Wikipedia's --lang flag" if serverSettings[ctx.guild.id]['wikipedia'] == True else ''}
            {"`   google:` Search through Google" if serverSettings[ctx.guild.id]['google'] == True else ''}
            {"`    image:` Google's Reverse Image Search with an image URL or image reply" if serverSettings[ctx.guild.id]['google'] == True else ''}
            {"`  scholar:` Search through Google Scholar" if serverSettings[ctx.guild.id]['scholar'] == True else ''}
            {"`  youtube:` Search through Youtube" if serverSettings[ctx.guild.id]['youtube'] == True else ''}
            {"`    anime:` Search through MyAnimeList" if serverSettings[ctx.guild.id]['mal'] == True else ''}
            {"`     xkcd:` Search for XKCD comics" if serverSettings[ctx.guild.id]['xkcd'] == True else ''}
        """))
        embed.set_footer(text=f"Do {commandPrefix}help [command] for more information")

        if args:
            if args[0] == 'sudo':
                embed = discord.Embed(title="Sudo", description=f"Admin commands. Server owner has sudo privilege by default.\nUsage: {commandPrefix}sudo [command] [args]")
                embed.add_field(name="Commands", inline=False, value=
                    f"""`     echo:` Have the bot say something. 
                        Args: message 
                        Optional flag: --channel [channelID]

                        `blacklist:` Block a user from using the bot. 
                        Args: userName OR userID 

                        `whitelist:` Unblock a user from using the bot. 
                        Args: userName OR userID

                        `   sudoer:` Add a user to the sudo list. Only guild owners can do this. 
                        Args: userName OR userID  

                        ` unsudoer:` Remove a user from the sudo list. Only guild owners can do this. 
                        Args: userName OR userID""")
            elif args[0] == 'log':
                embed = discord.Embed(title="Log", description=
                    f"DMs a .csv file of all the logs that the bot has for your username or guild if a sudoer.\nUsage: {commandPrefix}log")  
            elif args[0] == 'config':
                embed = discord.Embed(title="Guild Configuration", 
                    description="Views the guild configuration. Only sudoers can edit settings."+
                        "\nPrefix: Command prefix that SearchIO uses"+
                        "\nAdminrole: The role that is automatically given sudo permissions"+
                        "\nSafesearch: Activates Google's safesearch. NSFW channels override this setting"+
                        f"\nUsage: {commandPrefix}config [setting]")
            elif args[0] == 'wiki':
                embed = discord.Embed(title="Wikipedia", description=f"Wikipedia search. \nUsage: {commandPrefix}wiki [query] [flags]")
                embed.add_field(name="Optional Flags", inline=False, value=
                    f"""`--lang [ISO Language Code]:` Specifies a country code to search through Wikipedia. Use {commandPrefix}wikilang to see available codes""")
            elif args[0] == 'wikilang':
                embed = discord.Embed(title="WikiLang", description=
                """Lists Wikipedia's supported wikis in ISO codes. Common language codes are:
                    zh: 中文
                    es: Español
                    en: English
                    pt: Português
                    hi: हिन्दी
                    bn: বাংলা
                    ru: русский""")
            elif args[0] == 'google':
                embed = discord.Embed(title="Google", description=
                    f"Google search.\nUsage: {commandPrefix}google [query].\nIf a keyword is detected in [query], a special function will activate")
                embed.add_field(name="Keywords", inline=False, value=
                """`translate:` Uses Google Translate API to translate languages. 
                Input automatically detects language unless specified with 'from [language]' 
                Defaults to output English unless specified with 'to [language]'
                Example Query: translate مرحبا from arabic to spanish""")
            elif args[0] == 'image':
                embed = discord.Embed(title="Google Image", description=
                    f"Uses Google's Reverse Image search to output URLs that contain the image.\nUsage: {commandPrefix}image [imageURL] OR reply to an image in the chat")
            elif args[0] == 'scholar':
                embed = discord.Embed(title="GoogleScholar", description=
                    f"Google Scholar search. \nUsage: {commandPrefix}scholar [query] [flags].")
                embed.add_field(name="Flags", inline=False, value="""
                    `--author:` Use [query] to search for a specific author. Cannot be used with --cite
                    `  --cite:` Outputs a citation for [query] in BibTex. Cannot be used with --author""")        
            elif args[0] == 'youtube':
                embed = discord.Embed(title="Youtube", description=
                f"Searches through Youtube videos.\nUsage: {commandPrefix}youtube [query].")
            elif args[0] == 'anime':
                embed = discord.Embed(title="MyAnimeList", description=
                f"Searches through MyAnimeList\nUsage:{commandPrefix}anime [query]")
            elif args[0] == 'xkcd':
                embed = discord.Embed(title="XKCD", description=
                f"Searches for an XKCD comic\nUsage:{commandPrefix}anime [XKCD Comic #]")
            else: pass
        else: pass
        
        helpMessage = await ctx.send(embed=embed)
        try:
            await helpMessage.add_reaction('🗑️')
            reaction, user = await bot.wait_for("reaction_add", check=check, timeout=60)
            if str(reaction.emoji) == '🗑️':
                await helpMessage.delete()
                return
        
        except asyncio.TimeoutError as e: 
            await helpMessage.clear_reactions()
        
        finally: 
            return
    
    except Exception as e:
        ErrorHandler(bot, ctx, e, 'help', '')

class SearchEngines(commands.Cog, name="Search Engines"):
    def __init__(self, bot):
        self.bot = bot

    @commands.command(name = 'wiki')
    async def wikisearch(self, ctx, *args):
        global serverSettings
        if ctx.author.id not in serverSettings[ctx.guild.id]['blacklist'] and serverSettings[ctx.guild.id]['wikipedia'] != False:
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
    
    @commands.command(name = 'wikilang')
    async def wikilang(self, ctx):
        global serverSettings
        if ctx.author.id not in serverSettings[ctx.guild.id]['blacklist']:
            Log.appendToLog(ctx, 'wikilang')

            await WikipediaSearch(bot, ctx, "en").lang()
            return

    @commands.command(name = 'google')
    async def gsearch(self, ctx, *args):
        global serverSettings
        UserCancel = Exception
        if ctx.author.id not in serverSettings[ctx.guild.id]['blacklist'] and serverSettings[ctx.guild.id]['google'] != False:
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
                userquery = ' '.join(args).strip() #turns multiword search into single string.
            
            continueLoop = True
            
            while continueLoop==True:
                try:
                    message = await ctx.send(f'{LoadingMessage()} <a:loading:829119343580545074>')
                    messageEdit = asyncio.create_task(self.bot.wait_for('message_edit', check=lambda var, m: m.author == ctx.author, timeout=60))
                    search = asyncio.create_task(GoogleSearch.search(bot, ctx, serverSettings, message, userquery))
                    
                    #checks for message edit
                    waiting = [messageEdit, search]
                    done, waiting = await asyncio.wait(waiting, return_when=asyncio.FIRST_COMPLETED) # 30 seconds wait either reply or react

                    if messageEdit in done: #if the message is edited, the search is cancelled, message deleted, and command is restarted
                        if type(messageEdit.exception()) == asyncio.TimeoutError:
                            raise asyncio.TimeoutError
                        await message.delete()
                        messageEdit.cancel()
                        search.cancel()

                        messageEdit = messageEdit.result()
                        userquery = messageEdit[1].content.replace('&google ', '')
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

    @commands.command(name='image')
    async def image(self, ctx, *args):
        global serverSettings
        UserCancel = Exception
        if ctx.author.id not in serverSettings[ctx.guild.id]['blacklist'] and serverSettings[ctx.guild.id]['google'] != False:
            if ctx.message.reference:
                imagemsg = await ctx.fetch_message(ctx.message.reference.message_id)
                if imagemsg.attachments:
                    userquery = imagemsg.attachments[0].url

            elif not args: #checks if search is empty
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
                userquery = ' '.join(args).strip() #turns multiword search into single string

            search = ImageSearch(bot, ctx, userquery)
            await search.search()
            return

    @commands.command(name = 'scholar')   
    async def scholarsearch(self, ctx, *args):
        global serverSettings
        if ctx.author.id not in serverSettings[ctx.guild.id]['blacklist'] and serverSettings[ctx.guild.id]['scholar'] != False:
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
            else:
                args = ' '.join(list(args)).strip().split('--') #turns entire command into list split by flag operator
                userquery = args[0].strip()
                del args[0]

            search = ScholarSearch(bot, ctx, args, userquery)
            await search.search()
            return

    @commands.command(name = 'youtube')
    async def ytsearch(self, ctx, *args):
        global serverSettings
        UserCancel = Exception
        if ctx.author.id not in serverSettings[ctx.guild.id]['blacklist'] and serverSettings[ctx.guild.id]['youtube'] != False:
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
                userquery = ' '.join(args).strip() #turns multiword search into single string.

            search = YoutubeSearch(bot, ctx, userquery)
            await search.search()
            return

    @commands.command(name = 'anime')
    async def animesearch(self, ctx, *args):
        global serverSettings
        UserCancel = Exception
        if ctx.author.id not in serverSettings[ctx.guild.id]['blacklist'] and serverSettings[ctx.guild.id]['mal'] != False:
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
                userquery = ' '.join(args).strip() #turns multiword search into single string
            
            search = MyAnimeListSearch(bot, ctx, userquery)
            await search.search()
            return

    @commands.command(name = 'xkcd')
    async def xkcdsearch(self, ctx, *args):
        global serverSettings
        UserCancel = Exception
        if ctx.author.id not in serverSettings[ctx.guild.id]['blacklist'] and serverSettings[ctx.guild.id]['xkcd'] != False:
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
                userquery = ' '.join(args).strip() #turns multiword search into single string
            
            await XKCDSearch.search(bot, ctx, userquery)
            return
class Administration(commands.Cog, name="Administration"):
    def __init__(self, bot):
        self.bot = bot
    
    @commands.command(name='log')
    async def logging(self, ctx): 
        Log.appendToLog(ctx, 'log')
        await Log.logRequest(bot, ctx, serverSettings)
        return

    @commands.command(name='sudo')
    async def sudo(self, ctx, *args):
        global serverSettings
        args = list(args)
        if Sudo.isSudoer(bot, ctx, serverSettings) == False:
            await ctx.send(f"{ctx.author} is not in the sudoers file.  This incident will be reported.")
            Log.appendToLog(ctx, 'sudo', 'unauthorised')
        else:
            Log.appendToLog(ctx, "sudo", ' '.join(args).strip())
            command = Sudo(bot, ctx, serverSettings)
            await command.sudo(args)

        with open('serverSettings.json', 'r') as data:
            serverSettings = json.load(data, object_hook=lambda d: {int(k) if k.isdigit() else k: v for k, v in d.items()})
        return

    @commands.command(name='config')
    async def config(self, ctx, *args):
        args = list(args)
        global serverSettings
        command = Sudo(bot, ctx, serverSettings)
        if Sudo.isSudoer(bot, ctx, serverSettings) == True:
            await command.config(args)
        else: await command.config([])

        with open('serverSettings.json', 'r') as data:
            serverSettings = json.load(data, object_hook=lambda d: {int(k) if k.isdigit() else k: v for k, v in d.items()})
        return
    
bot.add_cog(SearchEngines(bot))
bot.add_cog(Administration(bot))

bot.run(DISCORD_TOKEN)
