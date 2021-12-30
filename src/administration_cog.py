from src.utils import Sudo, Log, error_handler
from discord.ext import commands
from time import time
import discord

class Administration(commands.Cog, name="Administration"):
    def __init__(self, bot):
        self.bot = bot
        return

    async def cog_before_invoke(self, ctx):
        self.bot.userSettings = Sudo.user_settings_check(self.bot.userSettings, ctx.author.id)
        Sudo.save_configs(self.bot)
        return

    @commands.command(
        name='log',
        brief='DMs a .csv file of all the logs that the bot has for your username or guild if a sudoer.',
        usage='log',
        aliases=['logs'])
    async def logging(self, ctx): 
        await Log.log_request(self.bot, ctx)
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

        if Sudo.is_sudoer(self.bot, ctx):
            Log.append_to_log(ctx, None, args)
            command = Sudo(self.bot, ctx)

            self.bot.serverSettings, self.bot.userSettings = await command.sudo(list(args))
            Sudo.save_configs(self.bot)
        else:
            await ctx.send(f"`{ctx.author}` is not in the sudoers file.  This incident will be reported.")
            Log.append_to_log(ctx, None, 'unauthorised')
        return

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
        
        command = Sudo(self.bot, ctx)
        if len(args) > 0:
            localSetting = args[0] in ['locale', 'alias']
        else: localSetting = False

        if Sudo.is_sudoer(self.bot, ctx) or localSetting:
            self.bot.serverSettings, self.bot.userSettings = await command.config(args)

        else: self.bot.serverSettings, self.bot.userSettings = await command.config([])
        Sudo.save_configs(self.bot)
        Log.append_to_log(ctx)

    @commands.command(
        name='invite',
        brief="DMs SearchIO's invite link to the user",
        usage='invite',
        help="DMs SearchIO's invite link to the user")
    async def invite(self, ctx):
        try:
            Log.append_to_log(ctx)
            dm = await ctx.author.create_dm()
            await dm.send(discord.utils.oauth_url(client_id=self.bot.botuser.id, permissions=discord.Permissions(4228381776), scopes=['bot','applications.commands']))
        except discord.errors.Forbidden:
            await ctx.send('Sorry, I cannot open a DM at this time. Please check your privacy settings')
        except Exception as e:
            await error_handler(self.bot, ctx, e)
        finally: return

    @commands.command(
        name='ping',
        brief="Sends SearchIO's DiscordAPI connection latency",
        usage='ping',
        help="Sends SearchIO's DiscordAPI connection latency")
    async def ping(self, ctx):
        try:
            beforeTime = time()
            message = await ctx.send('Testing')
            serverLatency = time() - beforeTime
            embed = discord.Embed(description='\n'.join(
                            [f'Message Send Time: `{round(serverLatency*1000, 2)}ms`',
                            f'API Heartbeat: `{round(self.bot.latency*100, 2)}ms`']))
            embed.set_footer(text=f'Requested by {ctx.author}')
            await message.edit(content=None, embed=embed)
        except Exception as e:
            await error_handler(self.bot, ctx, e)
        finally: return

def setup(bot):
    bot.add_cog(Administration(bot))
    return