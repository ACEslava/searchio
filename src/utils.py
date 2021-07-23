from datetime import datetime, timedelta, date

import asyncio
import csv
import difflib
from typing import Optional, Union, Tuple

import discord
import os
import random
import re
import traceback
from discord.errors import HTTPException
import yaml
from discord.ext import commands

from src.loadingmessage import get_loading_message


class Sudo:
    def __init__(
        self,
        bot: commands.Bot,
        ctx: commands.Context,
        server_settings: dict,
        user_settings: dict,
    ):

        self.bot = bot
        self.ctx = ctx
        self.server_settings = server_settings
        self.user_settings = user_settings

    # region database correction/query code
    @staticmethod
    def server_settings_check(server_settings: dict, server_id: int, bot: commands.Bot) -> dict:

        command_list = [
            command.name for command in dict(bot.cogs)["Search Engines"].get_commands()
        ]

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
            server_settings[server_id]["searchEngines"] = {
                key: True for key in command_list
            }

        # adds new search engines
        for searchEngines in command_list:
            if searchEngines not in server_settings[server_id]["searchEngines"].keys():
                server_settings[server_id]["searchEngines"][searchEngines] = True

        # removes old search engines
        delete_queue = [
            keys
            for keys in server_settings[server_id]["searchEngines"].keys()
            if keys not in command_list
        ]
        for keys in delete_queue:
            del server_settings[server_id]["searchEngines"][keys]

        return server_settings

    @staticmethod
    def user_settings_check(user_settings: dict, user_id: int) -> dict:
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
    def is_sudoer(bot: commands.Bot, ctx: commands.Context, server_settings: dict = None) -> bool:
        if server_settings is None:
            with open("serverSettings.yaml", "r") as data:
                server_settings = yaml.load(data, yaml.FullLoader)

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
        if ctx is None or ctx.guild is None:
            return "&"
        else:
            return server_settings[hex(ctx.guild.id)]["commandprefix"]

    @staticmethod
    def is_authorized_command(bot: commands.Bot, ctx: commands.Context, server_settings: dict) -> bool:
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
        return any([check, Sudo.is_sudoer(bot, ctx, server_settings)])

    async def user_search(self, search: Union[int, str]) -> Optional[discord.Member]:
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
                role = self.ctx.guild.get_role(int("".join(args)))
                if user is not None:
                    self.server_settings[hex(self.ctx.guild.id)]["blacklist"].append(
                        user.id
                    )
                    await self.ctx.send(f"`{str(user)}` blacklisted")
                
                elif role is not None:
                    self.server_settings[hex(self.ctx.guild.id)]["blacklist"].append(
                        role.id
                    )
                    
                    await self.ctx.send(
                        discord.Embed(
                            description=f"'{role.name}' is now blacklisted"
                        )
                    )
                
                else:
                    await self.ctx.send(
                        f"No user/role named `{''.join(args)}` was found in the guild"
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
                    role = self.ctx.guild.get_role(int("".join(args)))
                    if user is not None:
                        self.server_settings[hex(self.ctx.guild.id)][
                            "blacklist"
                        ].remove(user.id)
                        
                        await self.ctx.send(
                            discord.Embed(
                                description=f"`{str(user)}` removed from blacklist"
                            )
                        )
                    
                    elif role is not None:
                        
                        self.server_settings[hex(self.ctx.guild.id)][
                            "blacklist"
                        ].remove(role.id)
                        
                        await self.ctx.send(
                            discord.Embed(
                                description=f"'{role.name}' removed from blacklist"
                            )
                        )
                    else:
                        await self.ctx.send(
                            discord.Embed(
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
                or self.ctx.author.id == self.ctx.guild.owner_id
            ):
                user = await self.user_search(" ".join(args))
                if (
                    user.id
                    not in self.server_settings[hex(self.ctx.guild.id)]["sudoer"]
                ):
                    self.server_settings[hex(self.ctx.guild.id)]["sudoer"].append(
                        user.id
                    )
                    
                    await self.ctx.send(
                        discord.Embed(
                            description=f"`{str(user)}` is now a sudoer"
                        )
                    )
                else:
                    
                    await self.ctx.send(
                        discord.Embed(
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
                or self.ctx.author.id == self.ctx.guild.owner_id
            ):
                user = await self.user_search(" ".join(args))
                if user.id in self.server_settings[hex(self.ctx.guild.id)]["sudoer"]:
                    self.server_settings[hex(self.ctx.guild.id)]["sudoer"].remove(
                        user.id
                    )
                    await self.ctx.send(discord.Embed(description=f"`{str(user)}` has been removed from sudo"))
                else:
                    await self.ctx.send(discord.Embed(description=f"`{str(user)}` is not a sudoer"))
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
                embed = discord.Embed(
                    title="Sudo",
                    description=f"Admin commands. Server owner has sudo privilege by default.\n"
                    f"Usage: {self.print_prefix(self.server_settings)}sudo [command] [args]",
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
            return self.server_settings, self.user_settings

    async def config(self, args: list) -> Tuple[dict, dict]:
        def check(reaction_: discord.Reaction, user_: discord.User) -> bool:
            return user_ == self.ctx.author and str(reaction_.emoji) in ["✅", "❌"]

        UserCancel = KeyboardInterrupt
        try:
            # region config menu
            if not args:
                try:
                    embed = discord.Embed(title=f"{self.ctx.author} Configuration")
                    embed.add_field(
                        name="User Statistics",
                        value=f"""
                        `              Level:` {self.user_settings[self.ctx.author.id]['level']['rank']}
                        `                 XP:` {self.user_settings[self.ctx.author.id]['level']['xp']}/{self.user_settings[self.ctx.author.id]['level']['rank']*10}
                        `           Searches:` {(self.user_settings[self.ctx.author.id]['level']['rank']-1)*10+self.user_settings[self.ctx.author.id]['level']['xp']}
                        `   Daily Downloaded:` {self.user_settings[self.ctx.author.id]['downloadquota']['dailyDownload']}/50MB
                        `Lifetime Downloaded:` {self.user_settings[self.ctx.author.id]['downloadquota']['lifetimeDownload']}MB""",
                        inline=False,
                    )

                    embed.add_field(
                        name="User Configuration",
                        value=f"""
                        `             Locale:` {self.user_settings[self.ctx.author.id]['locale'] if self.user_settings[self.ctx.author.id]['locale'] is not None else 'None Set'}
                        `              Alias:` {self.user_settings[self.ctx.author.id]['searchAlias'] if self.user_settings[self.ctx.author.id]['searchAlias'] is not None else 'None Set'}""",
                        inline=False
                    )

                    embed.add_field(
                        name="Guild Administration",
                        value=f"""
                        ` adminrole:` {self.ctx.guild.get_role(self.server_settings[hex(self.ctx.guild.id)]['adminrole']) if self.server_settings[hex(self.ctx.guild.id)]['adminrole'] is not None else 'None set'}
                        `safesearch:` {'✅' if self.server_settings[hex(self.ctx.guild.id)]['safesearch'] == True else '❌'}
                        `    prefix:` {self.server_settings[hex(self.ctx.guild.id)]['commandprefix']}""",
                    )

                    embed.add_field(
                        name="Guild Search Engines",
                        value="\n".join(
                            [
                                f'`{command:>10}:` {"✅" if self.server_settings[hex(self.ctx.guild.id)]["searchEngines"][command] == True else "❌"}'
                                for command in [
                                    command.name
                                    for command in dict(self.bot.cogs)[
                                        "Search Engines"
                                    ].get_commands()
                                ]
                            ]
                        ),
                    )

                    embed.set_footer(
                        text=f"Do {self.print_prefix(self.server_settings)}config [setting] to change a specific setting"
                    )

                    embed.set_thumbnail(url=self.ctx.author.avatar_url)
                    config_message = await self.ctx.send(embed=embed)

                    await config_message.add_reaction("🗑️")
                    reaction, user = await self.bot.wait_for(
                        "reaction_add",
                        check=lambda reaction_, user_: all(
                            [
                                user_ == self.ctx.author,
                                str(reaction_.emoji) == "🗑️",
                                reaction_.message == config_message,
                            ]
                        ),
                        timeout=60,
                    )

                    if str(reaction.emoji) == "🗑️":
                        await config_message.delete()

                except asyncio.TimeoutError:
                    await config_message.clear_reactions()
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
                    embed = discord.Embed(
                        title=args[0],
                        description=f"{'✅' if self.server_settings[hex(self.ctx.guild.id)]['searchEngines'][args[0].lower()] == True else '❌'}",
                    )
                    embed.set_footer(text=f"React with ✅/❌ to enable/disable")
                    message = await self.ctx.send(embed=embed)
                    try:
                        await message.add_reaction("✅")
                        await message.add_reaction("❌")

                        reaction, user = await self.bot.wait_for(
                            "reaction_add", check=check, timeout=60
                        )
                        if str(reaction.emoji) == "✅":
                            self.server_settings[hex(self.ctx.guild.id)][
                                "searchEngines"
                            ][args[0].lower()] = True
                        elif str(reaction.emoji) == "❌":
                            self.server_settings[hex(self.ctx.guild.id)][
                                "searchEngines"
                            ][args[0].lower()] = False
                        await message.delete()
                        return
                    except asyncio.TimeoutError:
                        await message.clear_reactions()
                elif bool(
                    re.search("^enable", args[1].lower())
                    or re.search("^on", args[1].lower())
                ):
                    self.server_settings[hex(self.ctx.guild.id)]["searchEngines"][
                        args[0].lower()
                    ] = True
                elif bool(
                    re.search("^disable", args[1].lower())
                    or re.search("^off", args[1].lower())
                ):
                    self.server_settings[hex(self.ctx.guild.id)]["searchEngines"][
                        args[0].lower()
                    ] = False
                else:
                    embed = discord.Embed(
                        title=args[0].capitalize(),
                        description=f"{'✅' if self.server_settings[hex(self.ctx.guild.id)]['searchEngines'][args[0].lower()] == True else '❌'}",
                    )
                    embed.set_footer(text=f"React with ✅/❌ to enable/disable")
                    message = await self.ctx.send(embed=embed)

                    try:
                        await message.add_reaction("✅")
                        await message.add_reaction("❌")

                        reaction, user = await self.bot.wait_for(
                            "reaction_add", check=check, timeout=60
                        )
                        if str(reaction.emoji) == "✅":
                            self.server_settings[hex(self.ctx.guild.id)][
                                "searchEngines"
                            ][args[0].lower()] = True
                        elif str(reaction.emoji) == "❌":
                            self.server_settings[hex(self.ctx.guild.id)][
                                "searchEngines"
                            ][args[0].lower()] = False
                        await message.delete()
                        return
                    except asyncio.TimeoutError:
                        await message.clear_reactions()
                await self.ctx.send(
                    f"{args[0].capitalize()} is {'enabled' if self.server_settings[hex(self.ctx.guild.id)]['searchEngines'][args[0].lower()] == True else 'disabled'}"
                )
            elif args[0].lower() == "safesearch":
                if len(args) == 1:
                    embed = discord.Embed(
                        title=args[0],
                        description=f"{'✅' if self.server_settings[hex(self.ctx.guild.id)]['safesearch'] == True else '❌'}",
                    )
                    embed.set_footer(text=f"React with ✅/❌ to enable/disable")
                    message = await self.ctx.send(embed=embed)
                    try:
                        await message.add_reaction("✅")
                        await message.add_reaction("❌")

                        reaction, user = await self.bot.wait_for(
                            "reaction_add", check=check, timeout=60
                        )
                        if str(reaction.emoji) == "✅":
                            self.server_settings[hex(self.ctx.guild.id)][
                                "safesearch"
                            ] = True
                        elif str(reaction.emoji) == "❌":
                            self.server_settings[hex(self.ctx.guild.id)][
                                "safesearch"
                            ] = False
                        await message.delete()
                        return
                    except asyncio.TimeoutError:
                        await message.clear_reactions()
                elif bool(
                    re.search("^enable", args[1].lower())
                    or re.search("^on", args[1].lower())
                ):
                    self.server_settings[hex(self.ctx.guild.id)]["safesearch"] = True
                elif bool(
                    re.search("^disable", args[1].lower())
                    or re.search("^off", args[1].lower())
                ):
                    self.server_settings[hex(self.ctx.guild.id)]["safesearch"] = False
                else:
                    embed = discord.Embed(
                        title=args[0].capitalize(),
                        description=f"{'✅' if self.server_settings[hex(self.ctx.guild.id)]['safesearch'] == True else '❌'}",
                    )
                    embed.set_footer(text=f"React with ✅/❌ to enable/disable")
                    message = await self.ctx.send(embed=embed)

                    try:
                        await message.add_reaction("✅")
                        await message.add_reaction("❌")

                        reaction, user = await self.bot.wait_for(
                            "reaction_add", check=check, timeout=60
                        )
                        if str(reaction.emoji) == "✅":
                            self.server_settings[hex(self.ctx.guild.id)][
                                "safesearch"
                            ] = True
                        elif str(reaction.emoji) == "❌":
                            self.server_settings[hex(self.ctx.guild.id)][
                                "safesearch"
                            ] = False
                        await message.delete()
                        return
                    except asyncio.TimeoutError:
                        await message.clear_reactions()
                await self.ctx.send(
                    f"{args[0].capitalize()} is {'enabled' if self.server_settings[hex(self.ctx.guild.id)]['safesearch'] == True else 'disabled'}"
                )
            elif args[0].lower() == "adminrole":
                if len(args) == 1:
                    adminrole_id = self.server_settings[hex(self.ctx.guild.id)][
                        "adminrole"
                    ]

                    embed = discord.Embed(
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
                        self.server_settings[hex(self.ctx.guild.id)][
                            "adminrole"
                        ] = adminrole.id
                        await self.ctx.send(f"`{adminrole.name}` is now the admin role")
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
                                    for li in difflib.ndiff(
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
                    embed = discord.Embed(
                        title="Prefix",
                        description=f"{self.server_settings[hex(self.ctx.guild.id)]['commandprefix']}",
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

                self.server_settings[hex(self.ctx.guild.id)]["commandprefix"] = response
                await self.ctx.send(f"`{response}` is now the guild prefix")
            # endregion

            # region user config settings
            elif args[0].lower() == "locale":
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
                    embed = discord.Embed(
                        description=f"No results found for '{localequery}'"
                    )
                    await msg[0].edit(content=None, embed=embed)

                elif len(result) == 1:
                    self.user_settings[self.ctx.author.id]["locale"] = result[0]
                    await msg[0].edit(
                        content=f"Locale successfully set to `{result[0]}`"
                    )
                elif len(result) > 1:
                    result = [result[x : x + 10] for x in range(0, len(result), 10)]
                    pages = len(result)
                    cur_page = 1

                    if len(result) > 1:
                        embed = discord.Embed(
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
                        embed = discord.Embed(
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
                                embed = discord.Embed(
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
                                embed = discord.Embed(
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

                            self.user_settings[self.ctx.author.id]["locale"] = result[
                                cur_page - 1
                            ][input]
                            await self.ctx.send(
                                f"Locale successfully set to `{result[cur_page-1][input]}`"
                            )
                            break
            elif args[0].lower() == "alias":
                if len(args) == 1:
                    embed = discord.Embed(
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
                            self.user_settings[self.ctx.author.id]["searchAlias"] = None
                            await self.ctx.send(
                                f"Your alias has successfully been removed"
                            )
                        else:
                            getattr(dict(self.bot.cogs)["Search Engines"], response)
                            await self.ctx.send(f"`{response}` is now your alias")
                            self.user_settings[self.ctx.author.id][
                                "searchAlias"
                            ] = response
                        error_count = 2
                    except AttributeError:
                        embed = discord.Embed(
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

            return self.server_settings, self.user_settings
        except Exception as e:
            args = args if len(args) > 0 else None
            await error_handler(self.bot, self.ctx, e, args)
            return self.server_settings, self.user_settings
        finally:
            if args:
                Log.append_to_log(self.ctx, "config", args)
            return self.server_settings, self.user_settings


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
            writer = csv.DictWriter(
                file, fieldnames=log_fieldnames, extrasaction="ignore"
            )
            writer.writerow(
                dict(
                    zip(
                        log_fieldnames,
                        [
                            datetime.utcnow().isoformat(),
                            guild,
                            ctx.author.id,
                            str(ctx.author),
                            optcommand if optcommand is not None else ctx.command,
                            args,
                        ],
                    )
                )
            )
        return

    @staticmethod
    async def log_request(
        bot: commands.Bot,
        ctx: commands.Context,
        server_settings: dict,
        user_settings: dict,
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
                    for row in csv.DictReader(file)
                    if datetime.utcnow() - datetime.fromisoformat(dict(row)["Time"])
                    < timedelta(weeks=8)
                ]

            with open("logs.csv", "w", encoding="utf-8-sig") as file:
                writer = csv.DictWriter(
                    file, fieldnames=log_fieldnames, extrasaction="ignore"
                )
                writer.writeheader()
                writer.writerows(log_list)

            with open(f"./src/cache/{ctx.author}_userSettings.yaml", "w") as file:
                yaml.dump(user_settings[ctx.author.id], file, allow_unicode=True)

            # if bot owner
            if await bot.is_owner(ctx.author):
                dm = await ctx.author.create_dm()
                await dm.send(file=discord.File(r"logs.csv"))
                await dm.send(
                    file=discord.File(f"./src/cache/{ctx.author}_userSettings.yaml")
                )
            else:
                # if guild owner/guild sudoer
                if Sudo.is_sudoer(bot, ctx, server_settings):
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
                    writer = csv.DictWriter(
                        newFile, fieldnames=log_fieldnames, extrasaction="ignore"
                    )
                    writer.writeheader()
                    writer.writerows(line)

                dm = await ctx.author.create_dm()
                await dm.send(file=discord.File(f"./src/cache/{filename}.csv"))
                await dm.send(
                    file=discord.File(f"./src/cache/{ctx.author}_userSettings.yaml")
                )
                os.remove(f"./src/cache/{ctx.author}_userSettings.yaml")
                os.remove(f"./src/cache/{filename}.csv")

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
    if args is None:
        if ctx.args is None:
            args = "None"
        else:
            args = " ".join(list(ctx.args[2:]))
    elif isinstance(args, list):
        args = " ".join(args).strip()
    else:
        pass

    with open("logs.csv", "r", encoding="utf-8-sig") as file:
        does_error_code_match = True
        while does_error_code_match:
            error_code = "%06x" % random.randint(0, 0xFFFFFFFFFF)
            try:
                for line in csv.DictReader(file):
                    if line["Command"] == "error":
                        if line["Args"] == error_code:
                            does_error_code_match = True
                            break
                        else:
                            does_error_code_match = False
                    else:
                        continue
                does_error_code_match = False
            except Exception as e:
                print(e)

    Log.append_to_log(ctx, "error", error_code)

    # prevents doxxing by removing username
    error_out = "\n".join(
        [
            lines
            if r"C:\Users" not in lines
            else "\\".join(lines.split("\\")[:2] + lines.split("\\")[3:])
            for lines in str(traceback.format_exc()).split("\n")
        ]
    )

    # error message for the server
    embed = discord.Embed(
        description=f"An unknown error has occured, please try again later. \n If you wish to report this error, react with 🐛"
    )
    embed.set_footer(text=f"Error Code: {error_code}")
    error_msg = await ctx.send(embed=embed)
    await error_msg.add_reaction("🐛")

    try:
        # DMs a feedback form to the user
        response = None
        await bot.wait_for(
            "reaction_add",
            check=lambda reaction, user: user == ctx.author
            and str(reaction.emoji) == "🐛",
            timeout=60,
        )
        await error_msg.clear_reactions()
        dm = await ctx.author.create_dm()
        err_form = await dm.send(
            "Please send a message containing any feedback regarding this bug."
        )

        response = await bot.wait_for(
            "message",
            check=lambda m: m.author == ctx.author
            and isinstance(m.channel, discord.DMChannel),
            timeout=30,
        )
        response = response.content

        await dm.send(
            "Thank you for your feedback! If you want to see the status of SearchIO's bugs, join the Discord (https://discord.gg/fH4YTaGMRH).\nNote: this link is temporary"
        )
    except discord.errors.Forbidden:
        await error_msg.edit(
            embed=None,
            content="Sorry, I cannot open a DM at this time. Please check your privacy settings",
        )
    except TimeoutError:
        await err_form.delete()
    finally:
        # generates an error report for the tracker
        string = "\n".join(
            [
                f"Error `{error_code}`",
                f"```In Guild: {str(ctx.guild)} ({ctx.guild.id})",
                f"In Channel: {str(ctx.channel)} ({ctx.channel.id})",
                f"By User: {str(ctx.author)}({ctx.author.id})",
                f"Command: {ctx.command}",
                f"Args: {args if len(args) != 0 else 'None'}",
                f"{f'User Feedback: {response}' if response is not None else ''}",
                "\n" f"{error_out}```",
            ]
        )

        error_logging_channel = await bot.fetch_channel(829172391557070878)
        try:
            err_report = await error_logging_channel.send(string)
        except HTTPException as e:
            if e.code == 50035:
                with open(f"./src/cache/errorReport_{error_code}.txt", "w") as file:
                    file.write(error_out)
                
                string = "\n".join(
                    [
                        f"Error `{error_code}`",
                        f"```In Guild: {str(ctx.guild)} ({ctx.guild.id})",
                        f"In Channel: {str(ctx.channel)} ({ctx.channel.id})",
                        f"By User: {str(ctx.author)}({ctx.author.id})",
                        f"Command: {ctx.command}",
                        f"Args: {args if len(args) != 0 else 'None'}",
                        f"{f'User Feedback: {response}' if response is not None else ''}```"
                    ]
                )
                await error_logging_channel.send(string)
                await error_logging_channel.send(file=discord.File(f"./src/cache/errorReport_{error_code}.txt"))
                os.remove(f"./src/cache/errorReport_{error_code}.txt")
                return
                
        except Exception as e:
            print(e)
        await err_report.add_reaction("✅")
        return
