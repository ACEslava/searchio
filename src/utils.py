#External Dependencies
import asyncio

from concurrent.futures._base import TimeoutError
from csv import DictReader, DictWriter
from datetime import datetime, timedelta, date, timezone
from difflib import ndiff
from hashlib import sha1
from os import path as os_path
from os import remove as os_remove
from re import search as re_search
from requests import get
from traceback import format_exc
from typing import Optional, Union, Tuple
from yaml import load, dump, FullLoader

#Discord Modules
from discord import errors as discord_error
from discord import Message, Embed, Member, File, DMChannel
from discord import utils as discord_utils
from discord_components import Button, ButtonStyle, Select, SelectOption
from discord_components.interaction import Interaction
from discord_slash import SlashContext
from discord.ext import commands

#Utility Modules
from src.loadingmessage import get_loading_message

class Sudo:
    def __init__(
        self,
        bot: commands.Bot,
        ctx: commands.Context
    ):

        self.bot = bot
        self.ctx = ctx

    # region database correction/query code
    @staticmethod
    def server_settings_check(server_id: int, bot: commands.Bot) -> dict:
        '''Verifies if a serverSettings entry is valid.
        
        Args:
            server_id: int - Discord server ID
            bot: discord.commands.Bot
        
        Raises:
            None

        Returns:
            serverSettings: dict
        '''
        server_settings = bot.serverSettings
        server_id = hex(server_id)
        command_list = dict(bot.cogs)["Search Engines"].get_commands()

        if server_id not in server_settings.keys():
            server_settings[server_id] = {}

        keys = server_settings[server_id].keys()
        if "blacklist" not in keys:
            server_settings[server_id]["blacklist"] = []
        if "commandprefix" not in keys:
            server_settings[server_id]["commandprefix"] = "&"
        if "adminrole" not in keys:
            server_settings[server_id]["adminrole"] = None
        if "sudoer" not in keys:
            server_settings[server_id]["sudoer"] = []
        if "safesearch" not in keys:
            server_settings[server_id]["safesearch"] = False
        if "searchEngines" not in keys:
            server_settings_searchengines = {
                key: True for key in command_list
            }
        else:
            server_settings_searchengines = server_settings[server_id]["searchEngines"]    
        
        # adds new search engines
        for searchEngines in command_list:
            if searchEngines.name not in server_settings_searchengines.keys() and searchEngines.enabled is True:
                server_settings_searchengines[searchEngines.name] = True

        # removes old search engines
        command_list_names = [c.name for c in command_list]
        delete_queue = [
            keys
            for keys in server_settings_searchengines.keys()
            if keys not in command_list_names or not next((x for x in command_list if x.name == keys), None).enabled
            #^finds attribute in command_list with name key
        ]

        for keys in delete_queue:
            del server_settings_searchengines[keys]

        server_settings[server_id]['searchEngines'] = server_settings_searchengines
        return server_settings

    @staticmethod
    def user_settings_check(user_settings: dict, user_id: int) -> dict:
        '''Verifies if a userSettings entry is valid.

        Args:
            user_settings: dict - The userSettings dict
            user_id: int - Discord user ID

        Raises:
            None

        Returns:
            userSettings: dict
        '''

        if user_id not in user_settings.keys():
            user_settings[user_id] = {}

        keys = user_settings[user_id].keys()
        if "locale" not in keys:
            user_settings[user_id]["locale"] = None
        if "downloadquota" not in keys:
            user_settings[user_id]["downloadquota"] = {
                "updateTime": datetime.combine(
                    date.today(), datetime.min.time()
                ).isoformat(),
                "dailyDownload": 0,
                "lifetimeDownload": 0,
            }
        if "searchAlias" not in keys:
            user_settings[user_id]["searchAlias"] = None
        if "level" not in keys:
            user_settings[user_id]["level"] = {"rank":1, "xp":0}
        if datetime.utcnow() - datetime.fromisoformat(
            user_settings[user_id]["downloadquota"]["updateTime"]
        ) > timedelta(hours=24):
            user_settings[user_id]["downloadquota"]["updateTime"] = datetime.combine(
                date.today(), datetime.min.time()
            ).isoformat()

            if user_settings[user_id]["downloadquota"]["dailyDownload"] > 50:
                user_settings[user_id]["downloadquota"]["dailyDownload"] -= 50
            else:
                user_settings[user_id]["downloadquota"]["dailyDownload"] = 0

        return user_settings

    @staticmethod
    def is_sudoer(bot: commands.Bot, ctx: commands.Context) -> bool:
        '''Determines whether or not the context.author is a sudoer
        
        Args:
            bot: discord.commands.Bot
            ctx: discord.commands.Context

        Raises:
            None

        Returns:
            bool
        '''
        server_settings = bot.serverSettings
        if server_settings is None:
            with open("serverSettings.yaml", "r") as data:
                server_settings = load(data, FullLoader)

        # Checks if sudoer is owner
        is_owner = ctx.author.id == bot.owner_id

        # Checks if sudoer is server owner
        if ctx.guild:
            is_server_owner = ctx.author.id == ctx.guild.owner_id
        else:
            is_server_owner = False

        # Checks if sudoer has the designated adminrole or is a sudoer
        try:
            has_admin = server_settings[hex(ctx.guild.id)]["adminrole"] in [
                role.id for role in ctx.author.roles
            ]
            is_sudoer = ctx.author.id in server_settings[hex(ctx.guild.id)]["sudoer"]
        except Exception as e:
            print(e)
        finally:
            return any([is_owner, is_server_owner, has_admin, is_sudoer])

    @staticmethod
    def print_prefix(server_settings: dict, ctx: Optional[commands.Context] = None) -> str:
        '''Determines the guild-set prefix (or & if unset)
        
        Args:
            server_settings: dict - The serverSettings dict
            ctx: discord.commands.Context [Optional]

        Raises:
            None

        Returns:
            prefix: str
        '''
        if ctx is None or ctx.guild is None:
            return "&"
        else:
            return server_settings[hex(ctx.guild.id)]["commandprefix"]

    @staticmethod
    def is_authorized_command(bot: commands.Bot, ctx: Union[commands.Context, SlashContext]) -> bool:
        '''Determines whether or not the context.author is authorised to use the command
        
        Args:
            bot: discord.commands.Bot
            ctx: discord.commands.Context OR discord_slash.SlashContext

        Raises:
            None

        Returns:
            bool
        '''
        server_settings = bot.serverSettings
        if type(ctx) is SlashContext:
            role = next(
                (x for x in ctx.guild.roles if x.id == bot.serverSettings[hex(ctx.guild.id)]['blacklist']), 
                None
            )
            if ctx.command in ['translate', 'weather', 'define']:
                ctx.command = 'google'
            check = all(
                [
                    ctx.author.id not in server_settings[hex(ctx.guild.id)]["blacklist"],
                    ctx.author.id not in [m.id for m in role.members] if role is not None else True,
                    server_settings[hex(ctx.guild.id)]["searchEngines"][ctx.command]
                    is not False,
                ]
            )
        else:
            check = all(
                [
                    ctx.author.id not in server_settings[hex(ctx.guild.id)]["blacklist"],
                    not any(
                        role.id in server_settings[hex(ctx.guild.id)]["blacklist"]
                        for role in ctx.author.roles
                    ),
                    server_settings[hex(ctx.guild.id)]["searchEngines"][ctx.command.name]
                    is not False,
                ]
            )
        return any([check, Sudo.is_sudoer(bot, ctx)])

    @staticmethod
    def pageTurnCheck(
        bot: commands.Bot, 
        ctx: commands.Context, 
        button_ctx: Interaction, 
        message) -> bool:
        '''Determines whether or not the button interaction is from a permitted source

        Args:
            bot: discord.commands.Bot
            ctx: discord.commands.Context
            button_ctx: discord_components.context.Context
            message: discord.Message

        Raises:
            None

        Returns:
            bool
        '''
        server_settings = bot.serverSettings

        if server_settings is None:
            with open("serverSettings.yaml", "r") as data:
                server_settings = load(data, FullLoader)

        # Checks if sudoer is owner
        is_owner = button_ctx.author.id == bot.owner_id

        # Checks if sudoer is server owner
        if ctx.guild:
            is_server_owner = button_ctx.author.id == ctx.guild.owner_id
        else:
            is_server_owner = False

        # Checks if sudoer has the designated adminrole or is a sudoer
        try:
            role = discord_utils.find(
                lambda r: r.id == bot.serverSettings[hex(ctx.guild.id)]['adminrole'],
                ctx.guild.roles)
            has_admin = button_ctx.author.id in [m.id for m in role.members] if role is not None else False
            is_sudoer = button_ctx.author.id in server_settings[hex(ctx.guild.id)]["sudoer"]
        except Exception as e:
            print(e)
        finally:
            return all(
                [
                    (
                        button_ctx.author.id == ctx.author.id or 
                        any([is_owner, is_server_owner, has_admin, is_sudoer])
                    ),
                    button_ctx.message.id == message.id
                ]
            )
    
    @staticmethod
    async def multi_page_system(
        bot: commands.bot, 
        ctx: Union[commands.Context, SlashContext],
        message: Message, 
        embeds:'tuple[Embed]',
        components: 'list[tuple[Button,function]]') -> None:

        '''Handler for the multi-page system used by various search functions

        Args:
            bot: discord.commands.Bot
            ctx: discord.commands.Context OR discord_slash.SlashContext
            message: discord.Message
            embeds: list[Embed]
            emojis: dict[str:function]

        Raises:
            None

        Returns:
            None
        '''

        # multipage result display
        cur_page = 0

        await message.edit(
            content='',
            embed=embeds[cur_page % len(embeds)],
            components=[[list(di)[0] for di in i] for i in components]
        )
        
        components = {key.custom_id:value for i in components for di in i for (key,value) in di.items()}
        while 1:
            try:
                resp = await bot.wait_for(
                    "button_click",
                    check=lambda b_ctx: Sudo.pageTurnCheck(
                        bot=bot,
                        ctx=ctx,
                        button_ctx=b_ctx,
                        message=message
                    ),
                    timeout=60
                )

                if str(resp.custom_id) == "🗑️":
                    await message.delete()
                    return
                elif str(resp.custom_id) == "◀️":
                    cur_page -= 1
                elif str(resp.custom_id) == "▶️":
                    cur_page += 1
                elif str(resp.custom_id) in list(components.keys()):
                    if isinstance(components[str(resp.custom_id)], tuple):
                        await components[str(resp.custom_id)][0](*components[str(resp.custom_id)][1:])
                    else: await components[str(resp.custom_id)]()
                    return

                await resp.respond(
                    type=7,
                    content='',
                    embed=embeds[cur_page % len(embeds)]
                )

            except TimeoutError:
                await message.edit(
                    components=[]
                )
                return
    
    @staticmethod
    def save_configs(bot):
        '''Handler to save serverSettings and userSettings
        
        Args:
            bot: discord.commands.Bot
            
        Raises:
            None
            
        Returns:
            None'''
        with open("serverSettings.yaml", "w") as data:
            dump(bot.serverSettings, data, allow_unicode=True)
        print('Server settings saved')

        with open("userSettings.yaml", "w") as data:
            dump(bot.userSettings, data, allow_unicode=True)
        print('User settings saved')
        return
    
    async def user_search(self, search: Union[int, str]) -> Optional[Member]:
        '''Handler to search and return a discord.User object
        
        Args:
            search: int OR str
        
        Raises:
            Exception
            
        Returns:
            discord.User'''
        try:
            if search.isnumeric():
                return self.ctx.guild.get_member(int(search))
            else:
                return self.ctx.guild.get_member_named(search)

        except Exception:
            raise

    # endregion

    # region sudo functions
    async def echo(self, args: list) -> None:
        try:
            if "--channel" in args:
                channel = int(args[args.index("--channel") + 1])
                args.pop(args.index("--channel") + 1)
                args.pop(args.index("--channel"))

                if await self.bot.is_owner(self.ctx.author):
                    channel = await self.bot.fetch_channel(channel)
                else:  # Prevents non-owner sudoers from using bot in other servers
                    channel = self.ctx.guild.get_channel(channel)

            else:
                channel = self.ctx.channel

            await (channel or self.ctx).send(" ".join(args).strip())

        except Exception:
            raise
        finally:
            return

    async def blacklist(self, args: list) -> None:
        try:
            if len(args) == 1:
                user = await self.user_search(" ".join(args))
                role = self.ctx.guild \
                    .get_role(int("".join(args)))
                
                if user is not None:
                    self.bot.serverSettings \
                        [hex(self.ctx.guild.id)]["blacklist"] \
                        .append(user.id)
                    await self.ctx.send(
                        embed=Embed(
                            description=f"`{str(user)}` blacklisted"
                        )
                    )
                
                elif role is not None:
                    self.bot.serverSettings \
                        [hex(self.ctx.guild.id)]["blacklist"] \
                        .append(role.id)
                    
                    await self.ctx.send(
                        embed=Embed(
                            description=f"'{role.name}' is now blacklisted"
                        )
                    )
                
                else:
                    await self.ctx.send(
                        embed=Embed(
                            description=f"No user/role named `{''.join(args)}` was found in the guild"
                        )   
                    )
        except Exception:
            raise
        finally:
            return

    async def whitelist(self, args: list) -> None:
        try:
            if len(args) == 1:
                try:
                    user = await self.user_search(" ".join(args))
                    role = self.ctx.guild \
                        .get_role(int("".join(args)))
                    if user is not None:
                        self.bot.serverSettings \
                            [hex(self.ctx.guild.id)]["blacklist"] \
                            .remove(user.id)
                        
                        await self.ctx.send(
                            embed=Embed(
                                description=f"`{str(user)}` removed from blacklist"
                            )
                        )
                    
                    elif role is not None:
                        
                        self.bot.serverSettings \
                            [hex(self.ctx.guild.id)]["blacklist"] \
                            .remove(role.id)
                        
                        await self.ctx.send(
                            embed=Embed(
                                description=f"'{role.name}' removed from blacklist"
                            )
                        )
                    else:
                        await self.ctx.send(
                            embed=Embed(
                                description=f"No user/role with the ID `{''.join(args)}` was found in the guild"
                            )
                        )
                except ValueError:
                    await self.ctx.send(f"`{''.join(args)}` not in blacklist")
        except Exception:
            raise
        finally:
            return

    async def sudoer(self, args: list) -> None:
        try:
            if (
                self.ctx.author.id == self.bot.owner_id
                or self.ctx.author.id == self.ctx.guild.owner_id):

                user = await self.user_search(" ".join(args))
                if (
                    user.id
                    not in self.bot.serverSettings \
                        [hex(self.ctx.guild.id)]["sudoer"]):

                    self.bot.serverSettings \
                        [hex(self.ctx.guild.id)]["sudoer"] \
                        .append(user.id)
                    
                    await self.ctx.send(
                        embed=Embed(
                            description=f"`{str(user)}` is now a sudoer"
                        )
                    )
                else:
                    
                    await self.ctx.send(
                        embed=Embed(
                            description=f"`{str(user)}` is already a sudoer"
                        )
                    )
        except Exception:
            raise
        finally:
            return

    async def unsudoer(self, args: list) -> None:
        try:
            if (
                self.ctx.author.id == self.bot.owner_id
                or self.ctx.author.id == self.ctx.guild.owner_id):

                user = await self.user_search(" ".join(args))
                
                if user.id in self.bot.serverSettings \
                    [hex(self.ctx.guild.id)]["sudoer"]:
                    
                    self.bot.serverSettings \
                        [hex(self.ctx.guild.id)]["sudoer"] \
                        .remove(user.id)

                    await self.ctx.send(
                        embed=Embed(
                            description=f"`{str(user)}` has been removed from sudo"
                        )
                    )
                
                else:
                    await self.ctx.send(
                        embed=Embed(
                            description=f"`{str(user)}` is not a sudoer"
                        )
                    )
        except Exception:
            raise
        finally:
            return

    # endregion

    async def sudo(self, args):
        try:
            if args:
                command = args.pop(0)
                if command == "echo":
                    await self.echo(args)
                elif command == "blacklist":
                    await self.blacklist(args)
                elif command == "whitelist":
                    await self.whitelist(args)
                elif command == "sudoer":
                    await self.sudoer(args)
                elif command == "unsudoer":
                    await self.unsudoer(args)
                else:
                    await self.ctx.send(f"'{command}' is not a valid command.")
            else:
                embed = Embed(
                    title="Sudo",
                    description=f"Admin commands. Server owner has sudo privilege by default.\n"
                    f"Usage: {self.print_prefix(self.bot.serverSettings)}sudo [command] [args]",
                )
                embed.add_field(
                    name="Commands",
                    inline=False,
                    value=f"""`     echo:` Have the bot say something. 
                        Args: message 
                        Optional flag: --channel [channelID]

                        `blacklist:` Block a user from using the bot. 
                        Args: userName OR userID 

                        `whitelist:` Unblock a user from using the bot. 
                        Args: userName OR userID

                        `   sudoer:` Add a user to the sudo list. Only guild owners can do this. 
                        Args: userName OR userID  

                        ` unsudoer:` Remove a user from the sudo list. Only guild owners can do this. 
                        Args: userName OR userID""",
                )

                help_message = await self.ctx.send(embed=embed)
                try:
                    await help_message.add_reaction("🗑️")
                    reaction, _ = await self.bot.wait_for(
                        "reaction_add",
                        check=lambda reaction_, user_: all(
                            [
                                user_ == self.ctx.author,
                                str(reaction_.emoji) == "🗑️",
                                reaction_.message == help_message,
                            ]
                        ),
                        timeout=60,
                    )
                    if str(reaction.emoji) == "🗑️":
                        await help_message.delete()

                except asyncio.TimeoutError:
                    await help_message.clear_reactions()

        except Exception as e:
            args = args if len(args) > 0 else None
            await error_handler(self.bot, self.ctx, e, args)
        finally:
            return self.bot.serverSettings, self.bot.userSettings

    async def config(self, args: list) -> Tuple[dict, dict]:
        def check(button_ctx) -> bool:
            return button_ctx.author.id == self.ctx.author.id and button_ctx.message.id == message.id

        UserCancel = KeyboardInterrupt
        try:
            # region config menu
            if not args or args[0].isdigit():
                try:
                    if len(args)>0 and await self.user_search(args[0]) is not None and int(args[0]) in self.bot.userSettings.keys():
                        old_author = self.ctx.author
                        self.ctx.author = await self.user_search(args[0])
                    
                    levelInfo = self.bot.userSettings[self.ctx.author.id]['level']
                    level_arithmeticSum = int(((levelInfo['rank']-1)*10)/2*levelInfo['rank'])

                    userembed = Embed(title=f"{self.ctx.author} Configuration")
                    userembed.add_field(
                        name="User Statistics",
                        value=f"""
                        `              Level:` {levelInfo['rank']}
                        `                 XP:` {levelInfo['xp']}/{levelInfo['rank']*10}
                        `           Searches:` {level_arithmeticSum+levelInfo['xp']}
                        `   Daily Downloaded:` {self.bot.userSettings[self.ctx.author.id]['downloadquota']['dailyDownload']}/50MB
                        `Lifetime Downloaded:` {self.bot.userSettings[self.ctx.author.id]['downloadquota']['lifetimeDownload']}MB
                        `             Sudoer:` {'True' if Sudo.is_sudoer(self.bot, self.ctx) else 'False'}""",
                        inline=False,
                    )

                    userembed.add_field(
                        name="User Configuration",
                        value=f"""
                        `             Locale:` {self.bot.userSettings[self.ctx.author.id]['locale'] if self.bot.userSettings[self.ctx.author.id]['locale'] is not None else 'None Set'}
                        `              Alias:` {self.bot.userSettings[self.ctx.author.id]['searchAlias'] if self.bot.userSettings[self.ctx.author.id]['searchAlias'] is not None else 'None Set'}""",
                        inline=False
                    )

                    userembed.set_footer(
                        text=f"Do {self.print_prefix(self.bot.serverSettings)}config [setting] to change a specific setting"
                    )
                    
                    userembed.set_thumbnail(url=self.ctx.author.avatar_url)
                    
                    guildembed = Embed(title=f"{self.ctx.guild} Configuration")
                    guildembed.add_field(
                        name="Guild Administration",
                        value=f"""
                        ` adminrole:` {self.ctx.guild.get_role(self.bot.serverSettings[hex(self.ctx.guild.id)]['adminrole']) if self.bot.serverSettings[hex(self.ctx.guild.id)]['adminrole'] is not None else 'None set'}
                        `safesearch:` {'✅' if self.bot.serverSettings[hex(self.ctx.guild.id)]['safesearch'] == True else '❌'}
                        `    prefix:` {self.bot.serverSettings[hex(self.ctx.guild.id)]['commandprefix']}""",
                    )

                    guildembed.add_field(
                        name="Guild Search Engines",
                        value="\n".join(
                            [
                                f'`{command:>10}:` {"✅" if self.bot.serverSettings[hex(self.ctx.guild.id)]["searchEngines"][command] is True else "❌"}'
                                for command in [
                                    command.name
                                    for command in dict(self.bot.cogs)[
                                        "Search Engines"
                                    ].get_commands() if command.enabled
                                ]
                            ]
                        ),
                    )

                    guildembed.set_footer(
                        text=f"Do {self.print_prefix(self.bot.serverSettings)}config [setting] to change a specific setting"
                    )

                    guildembed.set_thumbnail(url=self.ctx.guild.icon_url)
                    
                    config_message = await self.ctx.send(
                        embed=userembed,
                        components=[
                            Select(placeholder="Page", options=[
                                SelectOption(label='Guild', value='guild'),
                                SelectOption(label='User', value='user')
                            ]),
                            Button(style=ButtonStyle.blue, label="🗑️", custom_id="🗑️")
                        ]
                    )
                    
                    while 1:
                        buttonresp = asyncio.create_task(self.bot.wait_for(
                            "button_click",
                            check=lambda button_ctx: all(
                                [
                                    button_ctx.author.id == old_author.id,
                                    button_ctx.message.id == config_message.id
                                ]
                            ),
                            timeout=60
                        ))
                        
                        selectresp = asyncio.create_task(self.bot.wait_for(
                            "select_option",
                            check=lambda i: all(
                                [
                                    i.author.id == old_author.id,
                                    i.message.id == config_message.id
                                ]
                            ),
                            timeout=60
                        ))
                        
                        waiting = [buttonresp, selectresp]
                        done, waiting = await asyncio.wait(
                            waiting, return_when=asyncio.FIRST_COMPLETED
                        )
                        
                        if buttonresp in done:
                            buttonresp = buttonresp.result()
                            if str(buttonresp.custom_id) == "🗑️":
                                await config_message.delete()
                                return
                        
                        elif selectresp in done:
                            selectresp = selectresp.result()
                            if str(selectresp.component[0].value) == "guild":
                                await selectresp.respond(
                                    type=7,
                                    content='',
                                    embed=guildembed
                                )
                            elif str(selectresp.component[0].value) == "user":
                                await selectresp.respond(
                                    type=7,
                                    content='',
                                    embed=userembed
                                )

                except TimeoutError:
                    await config_message.edit(
                        components=[]
                    )
                    pass
                except Exception as e:
                    await error_handler(self.bot, self.ctx, e)
                finally:
                    return
            # endregion

            # region config settings changers

            # region server config settings
            elif args[0].lower() in [
                command.name
                for command in dict(self.bot.cogs)["Search Engines"].get_commands()
            ]:
                if len(args) == 1:
                    embed = Embed(
                        title=args[0],
                        description=f"{'✅' if self.bot.serverSettings[hex(self.ctx.guild.id)]['searchEngines'][args[0].lower()] == True else '❌'}",
                    )

                    message = await self.ctx.send(
                        embed=embed,
                        components=[[
                            Button(style=ButtonStyle.green, label='Enable', custom_id='enable'),
                            Button(style=ButtonStyle.red, label='Disable', custom_id='disable')
                        ]]
                        )
                    try:
                        resp = await self.bot.wait_for(
                            "button_click",
                            check=check,
                            timeout=60
                        )

                        if str(resp.custom_id) == "enable":
                            self.bot.serverSettings[hex(self.ctx.guild.id)]["searchEngines"][args[0].lower()] = True
                        
                        elif str(resp.custom_id) == "disable":
                            self.bot.serverSettings[hex(self.ctx.guild.id)]["searchEngines"][args[0].lower()] = False
                        await resp.respond(
                            type=7,
                            embed=Embed(
                                description=f'{args[0].capitalize()} {"enabled" if resp.custom_id == "enable" else "disabled"}'
                            ),
                            components = []
                        )
                        return
                    except asyncio.TimeoutError:
                        pass
                elif bool(
                    re_search("^enable", args[1].lower())
                    or re_search("^on", args[1].lower())
                ):
                    self.bot.serverSettings[hex(self.ctx.guild.id)]["searchEngines"][
                        args[0].lower()
                    ] = True
                elif bool(
                    re_search("^disable", args[1].lower())
                    or re_search("^off", args[1].lower())
                ):
                    self.bot.serverSettings[hex(self.ctx.guild.id)]["searchEngines"][
                        args[0].lower()
                    ] = False
                else:
                    embed = Embed(
                        title=args[0],
                        description=f"{'✅' if self.bot.serverSettings[hex(self.ctx.guild.id)]['searchEngines'][args[0].lower()] == True else '❌'}",
                    )

                    message = await self.ctx.send(
                        embed=embed,
                        components=[[
                            Button(style=ButtonStyle.green, label='Enable', custom_id='enable'),
                            Button(style=ButtonStyle.red, label='Disable', custom_id='disable')
                        ]]
                        )
                    try:
                        resp = await self.bot.wait_for(
                            "button_click",
                            check=check,
                            timeout=60
                        )

                        if str(resp.custom_id) == "enable":
                            self.bot.serverSettings[hex(self.ctx.guild.id)]["searchEngines"][args[0].lower()] = True

                        elif str(resp.custom_id) == "disable":
                            self.bot.serverSettings[hex(self.ctx.guild.id)]["searchEngines"][args[0].lower()] = False
                        await resp.respond(
                            type=7,
                            embed=Embed(
                                description=f'{args[0].capitalized()} {"enabled" if resp.custom_id == "enable" else "disabled"}'
                            ),
                            components = []
                        )
                        return
                    except asyncio.TimeoutError:
                        pass
            elif args[0].lower() == "safesearch":
                if len(args) == 1:
                    embed = Embed(
                        title=args[0],
                        description=f"{'✅' if self.bot.serverSettings[hex(self.ctx.guild.id)]['safesearch'] == True else '❌'}",
                    )

                    message = await self.ctx.send(
                        embed=embed,
                        components=[[
                            Button(style=ButtonStyle.green, label='Enable', custom_id='enable'),
                            Button(style=ButtonStyle.red, label='Disable', custom_id='disable')
                        ]]
                        )
                    try:
                        resp = await self.bot.wait_for(
                            "button_click",
                            check=check,
                            timeout=60
                        )

                        if str(resp.custom_id) == "enable":
                            self.bot.serverSettings[hex(self.ctx.guild.id)]["safesearch"] = True

                        elif str(resp.custom_id) == "disable":
                            self.bot.serverSettings[hex(self.ctx.guild.id)]["safesearch"] = False
                        await resp.respond(
                            type=7,
                            embed=Embed(
                                description=f'Safesearch {"enabled" if resp.custom_id == "enable" else "disabled"}'
                            ),
                            components = []
                        )
                        return
                    except asyncio.TimeoutError:
                        pass
                elif bool(
                    re_search("^enable", args[1].lower())
                    or re_search("^on", args[1].lower())
                ):
                    self.bot.serverSettings[hex(self.ctx.guild.id)]["safesearch"] = True
                    await self.ctx.send(
                        embed=Embed(
                            description='Safesearch enabled'
                        ),
                    )
                elif bool(
                    re_search("^disable", args[1].lower())
                    or re_search("^off", args[1].lower())
                ):
                    self.bot.serverSettings[hex(self.ctx.guild.id)]["safesearch"] = False
                    await self.ctx.send(
                        embed=Embed(
                            description='Safesearch disabled'
                        ),
                    )
                else:
                    embed = Embed(
                        title=args[0],
                        description=f"{'✅' if self.bot.serverSettings[hex(self.ctx.guild.id)]['safesearch'] == True else '❌'}",
                    )

                    message = await self.ctx.send(
                        embed=embed,
                        components=[[
                            Button(style=ButtonStyle.green, label='Enable', custom_id='enable'),
                            Button(style=ButtonStyle.red, label='Disable', custom_id='disable')
                        ]]
                        )
                    try:
                        resp = await self.bot.wait_for(
                            "button_click",
                            check=check,
                            timeout=60
                        )

                        if str(resp.custom_id) == "enable":
                            self.bot.serverSettings[hex(self.ctx.guild.id)]["safesearch"] = True

                        elif str(resp.custom_id) == "disable":
                            self.bot.serverSettings[hex(self.ctx.guild.id)]["safesearch"] = False
                        await resp.respond(
                            type=7,
                            embed=Embed(
                                description=f'Safesearch {"enabled" if resp.custom_id == "enable" else "disabled"}'
                            ),
                            components = []
                        )
                        return
                    except asyncio.TimeoutError:
                        pass
            elif args[0].lower() == "adminrole":
                if len(args) == 1:
                    adminrole_id = self.bot.serverSettings[hex(self.ctx.guild.id)][
                        "adminrole"
                    ]

                    embed = Embed(
                        title="Adminrole",
                        description=f"{self.ctx.guild.get_role(int(adminrole_id)) if adminrole_id is not None else 'None set'}",
                    )
                    embed.set_footer(
                        text=f"Reply with the roleID of the role you want to set"
                    )
                    message = await self.ctx.send(embed=embed)

                    try:
                        userresponse = await self.bot.wait_for(
                            "message",
                            check=lambda m: m.author == self.ctx.author,
                            timeout=30,
                        )
                        await userresponse.delete()
                        await message.delete()
                        response = userresponse.content
                    except asyncio.TimeoutError:
                        return
                else:
                    response = args[1]

                error_count = 0
                while error_count <= 1:
                    try:
                        adminrole = self.ctx.guild.get_role(int(response))
                        self.bot.serverSettings[hex(self.ctx.guild.id)][
                            "adminrole"
                        ] = adminrole.id
                        await self.ctx.send(
                            embed=Embed(
                                description=f"`{adminrole.name}` is now the admin role"
                            )
                        )
                        break
                    except (ValueError, AttributeError):
                        error_msg = await self.ctx.send(
                            f"{response} is not a valid roleID. Please edit your message or reply with a valid roleID."
                        )
                        message_edit = asyncio.create_task(
                            self.bot.wait_for(
                                "message_edit",
                                check=lambda var, m: m.author == self.ctx.author,
                                timeout=60,
                            )
                        )
                        reply = asyncio.create_task(
                            self.bot.wait_for(
                                "message",
                                check=lambda m: m.author == self.ctx.author,
                                timeout=60,
                            )
                        )

                        waiting = [message_edit, reply]
                        done, waiting = await asyncio.wait(
                            waiting, return_when=asyncio.FIRST_COMPLETED
                        )  # 30 seconds wait either reply or react

                        if message_edit in done:
                            reply.cancel()
                            message_edit = message_edit.result()
                            response = "".join(
                                [
                                    li
                                    for li in ndiff(
                                        message_edit[0].content, message_edit[1].content
                                    )
                                    if "+" in li
                                ]
                            ).replace("+ ", "")
                        elif reply in done:
                            message_edit.cancel()
                            reply = reply.result()
                            await reply.delete()

                            if reply.content == "cancel":
                                message_edit.cancel()
                                reply.cancel()
                                break
                            else:
                                response = reply.content
                        await error_msg.delete()
                        error_count += 1
                        pass
            elif args[0].lower() == "prefix":
                if not args[1]:
                    embed = Embed(
                        title="Prefix",
                        description=f"{self.bot.serverSettings[hex(self.ctx.guild.id)]['commandprefix']}",
                    )
                    embed.set_footer(text=f"Reply with the prefix that you want to set")
                    message = await self.ctx.send(embed=embed)

                    try:
                        userresponse = await self.bot.wait_for(
                            "message",
                            check=lambda m: m.author == self.ctx.author,
                            timeout=30,
                        )
                        await userresponse.delete()
                        await message.delete()
                        response = userresponse.content

                    except asyncio.TimeoutError:
                        await message.delete()
                else:
                    response = args[1]

                self.bot.serverSettings[hex(self.ctx.guild.id)]["commandprefix"] = response
                await self.ctx.send(
                    embed=Embed(
                        description=f"`{response}` is now the guild prefix"
                    )
                )         
            # endregion

            # region user config settings
            elif args[0].lower() == "locale":
                if not os_path.exists('./src/cache/googleUULE.csv'):
                    with open('./src/cache/googleUULE.csv', 'w', encoding='utf-8-sig') as file:
                        file.write(
                            get('https://developers.google.com/adwords/api/docs/appendix/geo/geotargets-2021-04-16.csv').text
                        )
                msg = [
                    await self.ctx.send(
                        f"{get_loading_message()} <a:loading:829119343580545074>"
                    )
                ]
                uule_db = (
                    open("./src/cache/googleUULE.csv", "r", encoding="utf-8-sig")
                    .read()
                    .split("\n")
                )
                fieldnames = uule_db.pop(0).split(",")
                uule_db = [
                    dict(
                        zip(
                            fieldnames,
                            [string.replace('"', "") for string in lines.split('",')],
                        )
                    )
                    for lines in uule_db
                ]  # parses get request into list of dicts
                uule_db = [
                    placeDict
                    for placeDict in uule_db
                    if all(
                        [
                            "Name" in placeDict.keys(),
                            "Canonical Name" in placeDict.keys(),
                        ]
                    )
                ]

                if len(args) == 1:
                    ask_user = await self.ctx.send(
                        "Enter location or cancel to abort"
                    )  # if empty, asks user for search query
                    try:
                        localequery = await self.bot.wait_for(
                            "message",
                            check=lambda m: m.author == self.ctx.author,
                            timeout=30,
                        )  # 30 seconds to reply
                        await localequery.delete()
                        localequery = localequery.content
                        await ask_user.delete()
                        if localequery.lower() == "cancel":
                            raise UserCancel

                    except asyncio.TimeoutError:
                        await self.ctx.send(
                            f"{self.ctx.author.mention} Error: You took too long. Aborting"
                        )  # aborts if timeout
                else:
                    localequery = " ".join(args[1:]).strip()

                user_places = [
                    canonName
                    for canonName in uule_db
                    if localequery.lower() in canonName["Name"].lower()
                    and canonName["Status"] == "Active"
                ]  # searches uuleDB for locale query
                result = [canonName["Canonical Name"] for canonName in user_places]

                if len(result) == 0:
                    embed = Embed(
                        description=f"No results found for '{localequery}'"
                    )
                    await msg[0].edit(content=None, embed=embed)

                elif len(result) == 1:
                    self.bot.userSettings[self.ctx.author.id]["locale"] = result[0]
                    await msg[0].edit(
                        content=f"Locale successfully set to `{result[0]}`"
                    )
                elif len(result) > 1:
                    result = [result[x : x + 10] for x in range(0, len(result), 10)]
                    pages = len(result)
                    cur_page = 1

                    if len(result) > 1:
                        embed = Embed(
                            title=f"Locales matching '{localequery.capitalize()}'\n Page {cur_page}/{pages}:",
                            description="".join(
                                [
                                    f"[{index}]: {value}\n"
                                    for index, value in enumerate(result[cur_page - 1])
                                ]
                            ),
                        )
                        embed.set_footer(text=f"Requested by {self.ctx.author}")
                        await msg[0].edit(content=None, embed=embed)
                        await msg[-1].add_reaction("◀️")
                        await msg[-1].add_reaction("▶️")

                    else:
                        embed = Embed(
                            title=f"Locales matching '{localequery.capitalize()}':",
                            description="".join(
                                [
                                    f"[{index}]: {value}\n"
                                    for index, value in enumerate(result[0])
                                ]
                            ),
                        )
                        embed.set_footer(text=f"Requested by {self.ctx.author}")
                        await msg[0].edit(content=None, embed=embed)
                    msg.append(await self.ctx.send("Please choose option or cancel"))

                    while 1:
                        emojitask = asyncio.create_task(
                            self.bot.wait_for(
                                "reaction_add",
                                check=lambda reaction_, user_: all(
                                    [
                                        user_ == self.ctx.author,
                                        str(reaction_.emoji) in ["◀️", "▶️", "🗑️"],
                                        reaction_.message == msg[0],
                                    ]
                                ),
                                timeout=30,
                            )
                        )
                        responsetask = asyncio.create_task(
                            self.bot.wait_for(
                                "message",
                                check=lambda m: m.author == self.ctx.author,
                                timeout=30,
                            )
                        )
                        waiting = [emojitask, responsetask]
                        done, waiting = await asyncio.wait(
                            waiting, return_when=asyncio.FIRST_COMPLETED
                        )  # 30 seconds wait either reply or react

                        if emojitask in done:  # if reaction input, change page
                            reaction, user = emojitask.result()
                            if str(reaction.emoji) == "▶️" and cur_page != pages:
                                cur_page += 1
                                embed = Embed(
                                    title=f"Locales matching '{localequery.capitalize()}'\nPage {cur_page}/{pages}:",
                                    description="".join(
                                        [
                                            f"[{index}]: {value}\n"
                                            for index, value in enumerate(
                                                result[cur_page - 1]
                                            )
                                        ]
                                    ),
                                )
                                embed.set_footer(text=f"Requested by {self.ctx.author}")
                                await msg[-2].edit(embed=embed)
                                await msg[-2].remove_reaction(reaction, user)

                            elif str(reaction.emoji) == "◀️" and cur_page > 1:
                                cur_page -= 1
                                embed = Embed(
                                    title=f"Locales matching '{localequery.capitalize()}'\n Page {cur_page}/{pages}:",
                                    description="".join(
                                        [
                                            f"[{index}]: {value}\n"
                                            for index, value in enumerate(
                                                result[cur_page - 1]
                                            )
                                        ]
                                    ),
                                )
                                embed.set_footer(text=f"Requested by {self.ctx.author}")
                                await msg[-2].edit(embed=embed)
                                await msg[-2].remove_reaction(reaction, user)

                            else:
                                await msg[-2].remove_reaction(reaction, user)
                                # removes reactions if the user tries to go forward on the last page or
                                # backwards on the first page

                        elif responsetask in done:
                            emojitask.cancel()
                            input = responsetask.result()
                            await input.delete()
                            if input.content == "cancel":
                                raise UserCancel
                            elif input.content not in [
                                "0",
                                "1",
                                "2",
                                "3",
                                "4",
                                "5",
                                "6",
                                "7",
                                "8",
                                "9",
                            ]:
                                continue
                            input = int(input.content)

                            try:
                                for message in msg:
                                    await message.delete()
                            except:
                                pass

                            self.bot.userSettings[self.ctx.author.id]["locale"] = result[
                                cur_page - 1
                            ][input]
                            await self.ctx.send(
                                f"Locale successfully set to `{result[cur_page-1][input]}`"
                            )
                            break
            elif args[0].lower() == "alias":
                if len(args) == 1:
                    embed = Embed(
                        title="Alias",
                        description="Reply with the command that you want to set as alias. Choose from:\n{j}".format(
                            j="\n".join(
                                f"`{command.name}`"
                                for command in dict(self.bot.cogs)[
                                    "Search Engines"
                                ].get_commands()[0:-1]
                            )
                        ),
                    )
                    message = await self.ctx.send(embed=embed)

                    try:
                        userresponse = await self.bot.wait_for(
                            "message",
                            check=lambda m: m.author == self.ctx.author,
                            timeout=30,
                        )
                        await userresponse.delete()
                        await message.delete()
                        response = userresponse.content

                    except asyncio.TimeoutError:
                        await message.delete()
                        return
                else:
                    response = "".join(args[1])

                error_count = 0

                while error_count <= 1:
                    try:
                        if response == "s":
                            raise AttributeError
                        elif response.lower() == "none":
                            self.bot.userSettings[self.ctx.author.id]["searchAlias"] = None
                            await self.ctx.send(
                                f"Your alias has successfully been removed"
                            )
                        else:
                            getattr(dict(self.bot.cogs)["Search Engines"], response)
                            await self.ctx.send(f"`{response}` is now your alias")
                            self.bot.userSettings[self.ctx.author.id][
                                "searchAlias"
                            ] = response
                        error_count = 2
                    except AttributeError:
                        embed = Embed(
                            description=(
                                "Sorry, `{i}` is an invalid command.\n"
                                "Please choose from:\n"
                                "{j}\n"
                                "`none`\n"
                                "or cancel to cancel"
                            ).format(
                                i=response,
                                j="\n".join(
                                    f"`{command.name}`"
                                    for command in dict(self.bot.cogs)[
                                        "Search Engines"
                                    ].get_commands()[0:-1]
                                ),
                            )
                        )
                        error_msg = await self.ctx.send(embed=embed)
                        try:
                            message_edit = asyncio.create_task(
                                self.bot.wait_for(
                                    "message_edit",
                                    check=lambda m: m.author == self.ctx.author,
                                    timeout=60,
                                )
                            )

                            reply = asyncio.create_task(
                                self.bot.wait_for(
                                    "message",
                                    check=lambda m: m.author == self.ctx.author,
                                    timeout=60,
                                )
                            )

                            waiting = [message_edit, reply]
                            done, waiting = await asyncio.wait(
                                waiting, return_when=asyncio.FIRST_COMPLETED
                            )  # 30 seconds wait either reply or react

                            if message_edit in done:
                                reply.cancel()
                                message_edit = message_edit.result()[1].content
                                response = "".join(message_edit[14:])

                            elif reply in done:
                                message_edit.cancel()
                                reply = reply.result()
                                await reply.delete()

                                if reply.content == "cancel":
                                    message_edit.cancel()
                                    await error_msg.delete()
                                    break
                                else:
                                    response = reply.content
                            await error_msg.delete()
                            error_count += 1
                            continue

                        except asyncio.TimeoutError:
                            await error_msg.edit(content="Sorry you took too long")
                            await asyncio.sleep(60)
                            await error_msg.delete()
                            return
                return
            # endregion

            # endregion

        except UserCancel:
            await self.ctx.send("Aborting")
            if msg:
                for message in msg:
                    await message.delete()

            return self.bot.serverSettings, self.bot.userSettings
        except Exception as e:
            args = args if len(args) > 0 else None
            await error_handler(self.bot, self.ctx, e, args)
            return self.bot.serverSettings, self.bot.userSettings
        finally:
            if args:
                Log.append_to_log(self.ctx, "config", args)
            return self.bot.serverSettings, self.bot.userSettings

class Log:
    @staticmethod
    def append_to_log(
        ctx: commands.Context,
        optcommand: Optional[str] = None,
        args: Optional[Union[list, str]] = None,
    ):
        if args is None:
            if ctx.args is None:
                args = "None"
            else:
                args = " ".join(list(ctx.args[2:]))
        elif isinstance(args, list):
            args = " ".join(args).strip()
        else:
            pass

        log_fieldnames = ["Time", "Guild", "User", "User_Plaintext", "Command", "Args"]
        if ctx.guild:
            guild = ctx.guild.id
        else:
            guild = "DM"

        with open("logs.csv", "a", newline="", encoding="utf-8-sig") as file:
            writer = DictWriter(
                file, fieldnames=log_fieldnames, extrasaction="ignore"
            )
            try:
                writer.writerow(
                    dict(
                        zip(
                            log_fieldnames,
                            [
                                datetime.now(timezone.utc).isoformat(),
                                guild,
                                ctx.author.id,
                                str(ctx.author),
                                optcommand if optcommand is not None else ctx.command,
                                args,
                            ],
                        )
                    )
                )
            except Exception as e:
                print(e)
        return

    @staticmethod
    async def log_request(
        bot: commands.Bot,
        ctx: commands.Context
    ) -> None:
        try:
            log_fieldnames = [
                "Time",
                "Guild",
                "User",
                "User_Plaintext",
                "Command",
                "Args",
            ]

            with open("logs.csv", "r", encoding="utf-8-sig") as file:
                log_list = [
                    dict(row)
                    for row in DictReader(file)
                    if datetime.now(timezone.utc) - datetime.fromisoformat(dict(row)["Time"]) < timedelta(weeks=8)
                ]

            with open("logs.csv", "w", encoding="utf-8-sig") as file:
                writer = DictWriter(
                    file, fieldnames=log_fieldnames, extrasaction="ignore"
                )
                writer.writeheader()
                writer.writerows(log_list)

            with open(f"./src/cache/{ctx.author}_userSettings.yaml", "w") as file:
                dump(bot.userSettings[ctx.author.id], file, allow_unicode=True)

            # if bot owner
            if await bot.is_owner(ctx.author):
                dm = await ctx.author.create_dm()
                await dm.send(file=File(r"logs.csv"))
                await dm.send(
                    file=File(f"./src/cache/{ctx.author}_userSettings.yaml")
                )
            else:
                # if guild owner/guild sudoer
                if Sudo.is_sudoer(bot, ctx):
                    filename = f'{str(ctx.guild).replace(" ", "")}_guildLogs'
                    line = [
                        row
                        for row in log_list
                        if int(row["Guild"] if row["Guild"] != "DM" else "0")
                        == ctx.guild.id
                    ]

                # else just bot user
                else:
                    filename = f"{ctx.author}_personalLogs"
                    line = [
                        row for row in log_list if int(row["User"]) == ctx.author.id
                    ]

                with open(
                    f"./src/cache/{filename}.csv", "w", newline="", encoding="utf-8-sig"
                ) as newFile:
                    writer = DictWriter(
                        newFile, fieldnames=log_fieldnames, extrasaction="ignore"
                    )
                    writer.writeheader()
                    writer.writerows(line)

                dm = await ctx.author.create_dm()
                await dm.send(file=File(f"./src/cache/{filename}.csv"))
                await dm.send(
                    file=File(f"./src/cache/{ctx.author}_userSettings.yaml")
                )
                os_remove(f"./src/cache/{filename}.csv")
            
            os_remove(f"./src/cache/{ctx.author}_userSettings.yaml")

        except Exception as e:
            await error_handler(bot, ctx, e)
        finally:
            return

async def error_handler(
    bot: commands.Bot,
    ctx: commands.Context,
    error: Exception,
    args: Optional[Union[list, str]] = None,
) -> None:

    allowedErrors = [
        asyncio.CancelledError, 
        discord_error.NotFound,
        asyncio.TimeoutError
    ]

    if error in allowedErrors:
        return
    
    if args is None:
        if ctx.args is None:
            args = "None"
        else:
            args = " ".join(list(ctx.args[2:]))
    elif isinstance(args, list):
        args = " ".join(args).strip()
    else:
        pass
    
    #Unique string to each error code
    error_code = f'{int(sha1(str(error).encode("utf-8")).hexdigest()[0:2],16):03}.{sha1(str(format_exc()).encode("utf-8")).hexdigest()[0:6]}'
    Log.append_to_log(ctx, "error", error_code)

    # prevents doxxing by removing username
    error_out = "\n".join(
        [
            lines
            if r"C:\Users" not in lines
            else "\\".join(lines.split("\\")[:2] + lines.split("\\")[3:])
            for lines in str(format_exc()).split("\n")
        ]
    )
    if bot.devmode is False:
        # error message for the server
        embed = Embed(
            description=f"An unknown error has occured, please try again later."
        )
        embed.set_footer(text=f"Error Code: {error_code}")
        components = [[Button(style=ButtonStyle.red, label="Provide Feedback", custom_id="🐛")]]
        
        if await bot.is_owner(ctx.author):
            components[0].append(Button(style=ButtonStyle.gray, label="Display Error", custom_id="dev"))
            
        error_msg = await ctx.send(
            embed=embed,
            components=components
        )
        
        try:
            # DMs a feedback form to the user
            response = None
            resp = await bot.wait_for(
                "button_click",
                check=lambda b_ctx: b_ctx.user.id == ctx.author.id,
                timeout=60,
            )
            await error_msg.edit(components=[])
            
            if resp.custom_id == '🐛':
                dm = await ctx.author.create_dm()
                err_form = await dm.send(
                    f"Please send a message containing any feedback regarding Error `{error_code}`."
                )

                response = await bot.wait_for(
                    "message",
                    check=lambda m: m.author == ctx.author
                    and isinstance(m.channel, DMChannel),
                    timeout=30,
                )
                response = response.content

                await dm.send(
                    "Thank you for your feedback! If you want to see the status of SearchIO's bugs, join the Discord (https://discord.gg/fH4YTaGMRH).\nNote: this link is temporary"
                )
            
            elif resp.custom_id == 'dev':
                bot.devmode = True
        except discord_error.Forbidden:
            await error_msg.edit(
                embed=None,
                content="Sorry, I cannot open a DM at this time. Please check your privacy settings",
            )
        except TimeoutError:
            await err_form.delete()
    else:
        response = None
    #Error log in Discord server
    #changes alias to command used
    with open('userSettings.yaml', 'r') as data:
        userSettings = load(data, FullLoader)

    if ctx.command.name == 's' and userSettings[ctx.author.id]['searchAlias'] is not None:
        command = userSettings[ctx.author.id]['searchAlias']
    elif ctx.command.name == 's':
        command = 'alias unset'
    else:
        command = ctx.command

    # generates an error report for the tracker
    errstring = "\n".join(
        [
            f"Error `{error_code}`",
            f"```In Guild: {str(ctx.guild)} ({ctx.guild.id})",
            f"In Channel: {str(ctx.channel)} ({ctx.channel.id})",
            f"By User: {str(ctx.author)}({ctx.author.id})",
            f"Command: {command}",
            f"Args: {args if len(args) != 0 else 'None'}",
            f"{f'User Feedback: {response}' if response is not None else ''}",
            "\n" f"{error_out}```",
        ]
    )
    if bot.devmode is True:
        error_logging_channel = ctx.channel
        if resp.custom_id == 'dev': bot.devmode = False
    else:
        error_logging_channel = await bot.fetch_channel(829172391557070878)
    
    try:
        err_report = await error_logging_channel.send(errstring)
    except discord_error.HTTPException as e:
        if e.code == 50035:
            with open(f"./src/cache/errorReport_{error_code}.txt", "w") as file:
                file.write(error_out)
            
            err_report = await error_logging_channel.send(errstring)
            await error_logging_channel.send(file=File(f"./src/cache/errorReport_{error_code}.txt"))
            os_remove(f"./src/cache/errorReport_{error_code}.txt")
            
    except Exception as e:
        print(e)
    
    await err_report.add_reaction("✅")
    return
