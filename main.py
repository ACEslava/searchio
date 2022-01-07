#External Dependencies
from aiohttp import client_exceptions, ClientSession
from asyncio import ensure_future, get_event_loop, sleep
from asyncio import TimeoutError
from csv import DictReader, DictWriter
from datetime import datetime, timedelta, timezone
from dotenv import load_dotenv
from os import getenv
from os import path as os_path
from pathlib import Path
from shutil import rmtree
from yaml import load, dump, FullLoader

#Discord Modules
from discord import errors as discord_error
from discord import Intents, Embed, Activity, ActivityType, Permissions
from discord import utils as discord_utils
from discord_components import DiscordComponents
from discord_slash import SlashCommand
from discord.ext import commands, tasks

#Utility Modules
from src.utils import Sudo, error_handler

def main() -> None:
    def prefix(bot, message):   # handler for individual guild prefixes
        try:
            commandprefix: str = bot.serverSettings[hex(message.guild.id)]['commandprefix']
        except Exception:
            commandprefix:str = '&'
        finally: return commandprefix

    bot = commands.Bot(
        command_prefix=prefix, 
        intents=Intents.all(), 
        help_command=None)

    SlashCommand(
        bot, 
        sync_commands=True, 
        sync_on_cog_reload=True,
        override_type=True
    )

    #region filecheck code
    #checks if required files exist
    Path("./src/cache").mkdir(parents=True, exist_ok=True)

    if not os_path.exists('logs.csv'):
        with open('logs.csv', 'w') as file:
            file.write('Time,Guild,User,User_Plaintext,Command,Args')

    if not os_path.exists('serverSettings.yaml'):
        with open('serverSettings.yaml', 'w') as file:
            file.write('')

    if not os_path.exists('userSettings.yaml'):
        with open('userSettings.yaml', 'w') as file:
            file.write('')

    with open('serverSettings.yaml', 'r') as data:
        bot.serverSettings = load(data, FullLoader)
        if bot.serverSettings is None: bot.serverSettings = {}

    with open('userSettings.yaml', 'r') as data:
        bot.userSettings = load(data, FullLoader)
        if bot.userSettings is None: bot.userSettings = {}
    #endregion

    @bot.event
    async def on_guild_join(guild):
        #Creates new settings entry for guild
        Sudo.server_settings_check(hex(guild.id), bot)
        Sudo.save_configs(bot)

        owner = await bot.fetch_user(guild.owner_id)
        dm = await owner.create_dm()
        try:
            embed = Embed(title=f"Search.io was added to your server: '{guild.name}'.", 
                description = f"""
            Search.io is a bot that searches through multiple search engines/APIs.
            The activation command is `&`, and a list of various commands can be found using `&help`.
            
            • A list of admin commands can be found by using `&help sudo`. These commands may need ID numbers, which requires Developer Mode.
            • To turn on Developer Mode, go to Settings > Appearances > Advanced > Developer Mode. Then right click on users, roles, channels, or guilds to copy their ID.

            • Guild-specific settings can be accessed with `&config`
            • As a start, it is suggested to designate an administrator role that can use Search.io's sudo commands. Do `&config adminrole [roleID]` to designate an admin role.
            • You can change the command prefix with `&config prefix [character]`
            • You can also block or unblock specific commands with `&config [command]`
            • It is also suggested to turn on Safe Search, if needed. Do `&config safesearch on`. 

            • If you need to block a specific user from using Search.io, do `&sudo blacklist [userID]`. 
            • Unblock with `&sudo whitelist [userID]`

            If you have any problems with Search.io, join the help server: https://discord.gg/YB8VGYMZSQ""")
            await dm.send(embed=embed)
        
        except discord_error.Forbidden:
            pass
        finally: return

    @bot.event
    async def on_guild_remove(guild):
        del bot.serverSettings[hex(guild.id)]
        
        with open('serverSettings.yaml', 'w') as data:
            dump(bot.serverSettings, data, allow_unicode=True)
        return

    @bot.event
    async def on_connect():
        bot.botuser = await bot.application_info()
        await bot.change_presence(activity=Activity(type=ActivityType.listening, name="command prefix '&'"))

        DiscordComponents(bot)
        
        bot.load_extension('src.cogs.search_engine_cog')
        bot.load_extension('src.cogs.administration_cog')
        # bot.load_extension('src.administration_slashcog')
        # bot.load_extension('src.search_engine_slashcog')
        auto_save.start()
        cache_clear.start()

        #add new servers to settings
        for servers in bot.guilds:
            bot.serverSettings = Sudo.server_settings_check(servers.id, bot)

        #sets bot globals
        bot.devmode = False

        #remove old servers from settings
        delete_queue = []
        guild_list = [g.id for g in bot.guilds]
        for keys in bot.serverSettings.keys():
            if int(keys, 0) not in guild_list:
                delete_queue.append(keys)
        
        for keys in delete_queue:
            del bot.serverSettings[keys]

        Sudo.save_configs(bot)

        with open("logs.csv", "r", newline='', encoding='utf-8-sig') as file:
            lines = [dict(row) for row in DictReader(file) if datetime.now(timezone.utc)-datetime.fromisoformat(row["Time"]) < timedelta(weeks=8)]
            
        with open("logs.csv", "w", newline='', encoding='utf-8-sig') as file:
            logFieldnames = ["Time", "Guild", "User", "User_Plaintext", "Command", "Args"]
            writer = DictWriter(file, fieldnames=logFieldnames, extrasaction='ignore')
            writer.writeheader()
            writer.writerows(lines)         

        bot.session = ClientSession()
        return

    @bot.event
    async def on_command_error(ctx, error):
        if isinstance(error, commands.errors.CommandNotFound):
            await ctx.send(embed=
                Embed(
                    description=f"Command not found. Do {Sudo.print_prefix(bot.serverSettings, ctx)}help for available commands"
                )
            )

        elif isinstance(error, commands.CommandOnCooldown):
            await ctx.send(embed=
                Embed(
                    description=f"Command currently ratelimited. Please try again in {round(error.retry_after)+1}s."
                )
            )

        return
    
    @bot.command()
    async def help(ctx, *args):
        try:
            def check(reaction, user):
                return user == ctx.author and str(reaction.emoji) in ["🗑️"]
            commandPrefix = Sudo.print_prefix(bot.serverSettings, ctx)
            searchEngineCog = dict(bot.cogs)['Search Engines']
            adminCog = dict(bot.cogs)['Administration']

            maxAdminCommandStrLength = len(max([command.name for command in adminCog.get_commands()], key=len))
            args = list(args)

            embed = Embed(title="SearchIO", 
                description="Search.io is a bot that searches through multiple search engines/APIs.\nIt is developed by ACEslava#1984, K1NG#6219, and Nanu#3294")

            embed.add_field(name="Administration", inline=False, value="\n".join([f'`{command.name:>{maxAdminCommandStrLength}}:` {command.brief}' for command in adminCog.get_commands()]))

            embed.add_field(
                name="Search Engines", 
                inline=False, 
                value='\n'.join([f"`{command.name:>10}:` {command.brief}" 
                    for command in searchEngineCog.get_commands() 
                    if command.enabled is True
                    and bot.serverSettings[hex(ctx.guild.id)]['searchEngines'][command.name] is True]))

            embed.set_footer(text=f"Do {commandPrefix}help [command] for more information")

            if args:
                try:
                    command = getattr(searchEngineCog, args[0].lower())
                except AttributeError:
                    try: command = getattr(adminCog, args[0].lower())
                    except AttributeError: command = None

                if command is not None:
                    embed = Embed(title=command.name, 
                        description=f"""
                        {command.help}
                        Usage:
                        ```{command.usage}```
                        {'Optionals:```'+command.description+'```' if command.description != '' else ''}""")
                    embed.set_footer(text=f"Requested by {ctx.author}")
                    helpMessage = await ctx.send(embed=embed)
                    try:
                        await helpMessage.add_reaction('🗑️')
                        reaction, _ = await bot.wait_for("reaction_add", check=check, timeout=60)
                        if str(reaction.emoji) == '🗑️':
                            await helpMessage.delete()
                            return

                    except TimeoutError as e: 
                        await helpMessage.clear_reactions()
                else: pass
            else:
                invite_link=discord_utils.oauth_url(
                    client_id=bot.botuser.id, 
                    permissions=Permissions(4228381776), 
                    scopes=['bot','applications.commands']
                )
                dm = await ctx.author.create_dm()
                await dm.send(embed=embed)
                await dm.send('\n'.join(['If you have further questions, feel free to join the support server: https://discord.gg/YB8VGYMZSQ',
                f'Want to add the bot to your server? Use this invite link: {invite_link}']))

        except discord_error.Forbidden:
            await ctx.send(
                embed=Embed(
                    description='Sorry, I cannot open a DM at this time. Please check your privacy settings'
                )
            )

        except Exception as e:
            await error_handler(bot, ctx, e)
        finally: return

    @bot.command(hidden=True)
    @commands.is_owner()
    async def dev(ctx, *args):
        args = ' '.join([x.strip() for x in list(args)]).split()
        try:
            if args[0] == 'debug':
                bot.devmode = eval(args[1])
                await ctx.send(
                    embed=Embed(
                        description=f'debug log {"enabled" if bot.devmode else "disabled"}'
                    )
                )

            elif args[0] == 'reload':
                cog = args[1]
                bot.reload_extension(cog)
                await ctx.send(embed=Embed(description=f'{cog} successfully reloaded'))
            
            elif args[0] == 'unload':
                cog = args[1]
                bot.unload_extension(cog)
                await ctx.send(embed=Embed(description=f'{cog} successfully unloaded'))

            elif args[0] == 'load':
                cog = args[1]
                bot.load_extension(cog)
                await ctx.send(embed=Embed(description=f'{cog} successfully loaded'))
            
            elif args[0] == 'error':      
                with open("logs.csv", "r", encoding="utf-8-sig") as file:
                    reporters = [int(row['User']) for row in list(DictReader(file)) if row["Command"] == 'error' and row["Args"] == args[1]]
    
                for r in reporters:
                    user = await bot.fetch_user(r)
                    dm = await user.create_dm()
                    await dm.send(embed=Embed(title=f'Error {args[1]}', description=f'Marked as {args[2]} by {ctx.author}'))
                await ctx.send(embed=Embed(description=f'Error reporters notified'))
                
        except (commands.ExtensionNotFound, commands.ExtensionNotLoaded):
            await ctx.send(embed=Embed(description=f'{cog} not found'))

        except commands.errors.ExtensionAlreadyLoaded:
            await ctx.send(embed=Embed(description=f'{cog} already loaded'))
        
        except discord_error.Forbidden:  
            await ctx.send(embed=Embed(description=f"Can't open DM to user"))
        
        except Exception as e:
            await error_handler(bot, ctx, e, args)
        finally: return

    @tasks.loop(minutes=60.0)
    async def auto_save():
        Sudo.save_configs(bot)
        return
    
    @tasks.loop(minutes=120.0)
    async def cache_clear():
        rmtree('./src/cache')
        Path("./src/cache").mkdir(parents=True, exist_ok=True)
        return

    load_dotenv()

    async def startup():
        while 1:
            try:
                await bot.login(token=getenv("DISCORD_TOKEN"), bot=True)
                await bot.connect(reconnect=True)
            except (discord_error.ConnectionClosed, client_exceptions.ClientConnectorError):
                await sleep(10)
                continue
    
    ensure_future(startup())
    get_event_loop().run_forever()
    return

if __name__ == "__main__":
    main()
